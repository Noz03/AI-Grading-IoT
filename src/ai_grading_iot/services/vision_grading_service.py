"""Authorized Vision grading with stale-result rejection and component-only merges."""
import io
import json
import logging
import warnings
from pathlib import Path
from uuid import UUID, uuid4

from PIL import Image, UnidentifiedImageError
from sqlalchemy.exc import IntegrityError

from ai_grading_iot.clients.groq_client import GroqClient
from ai_grading_iot.core.config import get_settings
from ai_grading_iot.graders.vision_grader import VisionGrader
from ai_grading_iot.services.grading_service import GradingConflict, GradingNotFound, GradingService
from ai_grading_iot.services.image_storage_service import MAX_BYTES, ImageStorageError, ImageStorageService
from ai_grading_iot.services.score_aggregation import aggregate_scores
from ai_grading_iot.services.yolo_inference_service import YOLOInferenceService

logger = logging.getLogger(__name__)


class VisionStorageError(Exception):
    pass


class VisionArtifactError(Exception):
    pass


class VisionGradingService(GradingService):
    def __init__(self, db, *, inference=None, grader=None, storage=None):
        super().__init__(db)
        self.inference = inference
        self.grader = grader
        self.storage = storage or ImageStorageService()

    def _images(self, submission):
        settings = get_settings()
        if not 1 <= settings.VISION_MAX_IMAGES <= 5 or len(submission.images) > settings.VISION_MAX_IMAGES:
            raise GradingConflict("Invalid Vision image count")
        images = []
        for reference in submission.images:
            try:
                expected_prefix = f"submissions/{submission.id}/"
                if not reference.startswith(expected_prefix):
                    raise VisionStorageError("Stored image integrity failure")
                image_id = UUID(Path(reference).stem)
                payload = self.storage.read(reference)
                if len(payload) > MAX_BYTES:
                    raise VisionStorageError("Stored image integrity failure")
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(io.BytesIO(payload)) as image:
                        image.load()
                images.append((image_id, payload))
            except (ValueError, OSError, UnidentifiedImageError, ImageStorageError,
                    Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
                logger.warning("Stored Vision image integrity failure for submission %s", submission.id)
                raise VisionStorageError("Stored image integrity failure") from exc
        return images

    def _artifact_reference(self, submission_id, revision, run_id, image_id):
        return f"grading_artifacts/{submission_id}/{revision}/{run_id}/{image_id}-annotated.png"

    def _artifact_path(self, reference: str):
        parts = Path(reference).parts
        try:
            if len(parts) != 5 or parts[0] != "grading_artifacts":
                raise ValueError
            UUID(parts[1]); int(parts[2]); UUID(parts[3])
            UUID(parts[4].removesuffix("-annotated.png"))
            if not parts[4].endswith("-annotated.png"):
                raise ValueError
            path = self.storage.root.joinpath(*parts)
            if not path.resolve().is_relative_to(self.storage.root) or path.is_symlink():
                raise ValueError
            return path
        except ValueError as exc:
            raise VisionStorageError("Vision artifact not found") from exc

    def grade_vision(self, submission_id: UUID, actor, *, regrade=False):
        submission, practice = self._context(submission_id, actor, regrade=regrade)
        if submission.status != "submitted":
            raise GradingConflict("Only submitted Submissions can be graded")
        rubrics, signature = self._rubric_snapshot(practice)
        existing = self.results.get_by_submission(submission_id)
        if regrade and (existing is None or existing.vision_evaluation is None):
            raise GradingNotFound
        if not regrade and existing is not None and existing.vision_evaluation is not None:
            raise GradingConflict("Vision Evaluation already exists")
        original_vision = json.dumps(existing.vision_evaluation, sort_keys=True) if existing and regrade else None
        if rubrics["vision"].weight == 0:
            raise GradingConflict("Vision Rubric is not applicable")
        revision, references = submission.revision, list(submission.images)
        practice_input = self.practices.to_schema(practice)
        images = self._images(submission)
        self.db.rollback()

        produced = []
        if images:
            try:
                inference = self.inference or YOLOInferenceService()
                for image_id, payload in images:
                    detections, annotated = inference.infer(image_id, payload)
                    if detections.image_id != image_id:
                        raise ValueError("Inference image mismatch")
                    produced.append((detections, payload, annotated))
                settings = get_settings()
                grader = self.grader or VisionGrader(
                    GroqClient(model_name=settings.VISION_GROQ_MODEL),
                    settings.VISION_GROQ_MODEL, settings.VISION_GROQ_TIMEOUT_SECONDS)
                aggregate, observations = grader.grade(practice_input, rubrics["vision"], produced)
            except Exception:
                self.db.rollback()
                raise
        else:
            from ai_grading_iot.schemas.vision import AggregateEvaluation
            aggregate = AggregateEvaluation(score=None, evidence_status="insufficient",
                                            feedback="No Submission images were provided.", criteria_feedback=[])
            observations = []

        run_id = uuid4()
        written = []
        committed = False
        try:
            artifacts = {}
            for detections, _, annotated in produced:
                reference = self._artifact_reference(submission_id, revision, run_id, detections.image_id)
                path = self._artifact_path(reference)
                path.parent.mkdir(parents=True, exist_ok=True)
                # Unique run ID prevents replacement of existing grading evidence.
                with path.open("xb") as handle:
                    written.append(path)
                    handle.write(annotated)
                artifacts[str(detections.image_id)] = reference
            evaluation = {**aggregate.model_dump(mode="json"),
                          "image_ids": [str(image_id) for image_id, _ in images],
                          "model_version": produced[0][0].model_version if produced else None,
                          "qwen_model": get_settings().VISION_GROQ_MODEL if images else None,
                          "detections": [item[0].model_dump(mode="json") for item in produced],
                          "image_evaluations": [item.model_dump(mode="json") for item in observations],
                          "artifacts": artifacts, "submission_revision": revision}
            current, current_practice = self._context(submission_id, actor, regrade=regrade, lock=True)
            if current.status != "submitted" or current.revision != revision or current.images != references:
                raise GradingConflict("Submission changed during Vision grading")
            current_practice = self.practices.get_for_update(current.practice_id)
            _, current_signature = self._rubric_snapshot(current_practice)
            if signature != current_signature:
                raise GradingConflict("Practice or Rubrics changed during Vision grading")
            stored = self.results.get_by_submission(submission_id)
            if regrade and (stored is None or stored.vision_evaluation is None or
                            json.dumps(stored.vision_evaluation, sort_keys=True) != original_vision):
                raise GradingConflict("Vision Evaluation changed during regrade")
            if not regrade and stored is not None and stored.vision_evaluation is not None:
                raise GradingConflict("Vision Evaluation already exists")
            code_score = stored.code_score if stored else None
            data_score = stored.data_score if stored else None
            final = aggregate_scores({key: item.weight for key, item in rubrics.items()},
                                     {"code": code_score, "data": data_score, "vision": aggregate.score})
            if stored is None:
                stored = self.results.create(submission_id=submission_id, vision_score=aggregate.score,
                                             final_score=final, vision_evaluation=evaluation)
            else:
                stored.vision_score = aggregate.score
                stored.vision_evaluation = evaluation
                stored.final_score = final
                from datetime import datetime, timezone
                stored.graded_at = datetime.now(timezone.utc)
                self.db.flush()
            result = self.results.to_schema(stored)
            self.db.commit()
            committed = True
            return result
        except IntegrityError as exc:
            self.db.rollback()
            raise GradingConflict("Concurrent grading conflict") from exc
        except OSError as exc:
            self.db.rollback()
            raise VisionArtifactError("Vision artifact persistence failed") from exc
        except Exception:
            self.db.rollback()
            raise
        finally:
            if not committed:
                for path in written:
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        logger.exception("Failed to clean up Vision artifact")

    def _current(self, submission_id, actor):
        submission, _ = self._context(submission_id, actor)
        result = self.results.get_by_submission(submission_id)
        if result is None or result.vision_evaluation is None or result.vision_evaluation.get("submission_revision") != submission.revision:
            raise GradingNotFound
        return result

    def result(self, submission_id, actor):
        return self.results.to_schema(self._current(submission_id, actor))

    def detections(self, submission_id, actor):
        return self._current(submission_id, actor).vision_evaluation["detections"]

    def artifact(self, submission_id, image_id, actor):
        evaluation = self._current(submission_id, actor).vision_evaluation
        reference = evaluation.get("artifacts", {}).get(str(image_id))
        if not reference:
            raise GradingNotFound
        path = self._artifact_path(reference)
        try:
            return path.read_bytes()
        except OSError as exc:
            raise GradingNotFound from exc
