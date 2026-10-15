"""Authorized grading with no open database transaction during provider calls."""
import json
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_grading_iot.clients.groq_client import GroqClient
from ai_grading_iot.graders.code_grader import CodeGrader
from ai_grading_iot.graders.data_grader import DataGrader
from ai_grading_iot.repositories.course_repository import CourseRepository
from ai_grading_iot.repositories.grading_repository import GradingRepository
from ai_grading_iot.repositories.practice_repository import PracticeRepository
from ai_grading_iot.repositories.rubric_repository import RubricRepository
from ai_grading_iot.repositories.submission_repository import SubmissionRepository
from ai_grading_iot.schemas.grading_result import GradingResult
from ai_grading_iot.schemas.rubric import Rubric
from ai_grading_iot.services.score_aggregation import aggregate_scores


class GradingConflict(Exception):
    pass


class GradingNotFound(Exception):
    pass


class GradingService:
    def __init__(self, db: Session, code_grader=None, data_grader=None):
        self.db = db
        self.submissions = SubmissionRepository(db)
        self.practices = PracticeRepository(db)
        self.rubrics = RubricRepository(db)
        self.courses = CourseRepository(db)
        self.results = GradingRepository(db)
        self.code_grader = code_grader
        self.data_grader = data_grader

    def _context(self, submission_id: UUID, actor, *, regrade=False, lock=False):
        submission = self.submissions.get_for_update(submission_id) if lock else self.submissions.get_by_id(submission_id)
        if submission is None:
            raise GradingNotFound
        practice = self.practices.get_by_id(submission.practice_id)
        if practice is None:
            raise GradingNotFound
        if actor.role == "admin":
            pass
        elif actor.role == "teacher" and self.courses.has_membership(practice.course_id, actor.id, "teacher"):
            pass
        elif not regrade and actor.role == "student" and submission.student_id == actor.id and self.courses.has_membership(practice.course_id, actor.id, "student"):
            pass
        else:
            raise PermissionError
        return submission, practice

    def _rubric_snapshot(self, practice):
        rows = self.rubrics.get_by_practice(practice.id)
        if len(rows) != 3 or {row.type for row in rows} != {"code", "data", "vision"}:
            raise GradingConflict("Practice requires Code, Data and Vision Rubrics")
        references = practice.rubric_reference
        expected = {"code": references.get("code_rubric_id"), "data": references.get("dashboard_rubric_id"), "vision": references.get("vision_rubric_id")}
        if any(str(row.id) != str(expected[row.type]) for row in rows):
            raise GradingConflict("Practice Rubric references are inconsistent")
        try:
            rubrics = {row.type: self.rubrics.to_schema(row) for row in rows}
            aggregate_scores({key: item.weight for key, item in rubrics.items()}, {key: None for key in rubrics})
        except (ValidationError, ValueError) as exc:
            raise GradingConflict("Invalid Practice Rubrics") from exc
        signature = json.dumps({"practice": self.practices.to_schema(practice).model_dump(mode="json"),
                                "rubrics": {key: item.model_dump(mode="json") for key, item in rubrics.items()}}, sort_keys=True)
        return rubrics, signature

    def grade(self, submission_id: UUID, actor, *, regrade=False) -> GradingResult:
        actor_id, actor_role = actor.id, actor.role
        submission, practice = self._context(submission_id, actor, regrade=regrade)
        if submission.status != "submitted":
            raise GradingConflict("Only submitted Submissions can be graded")
        existing = self.results.get_by_submission(submission_id)
        if regrade and existing is None:
            raise GradingNotFound
        if not regrade and existing is not None and (existing.code_evaluation is not None or existing.data_evaluation is not None):
            raise GradingConflict("Code/Data Evaluation already exists")
        original_result_id = existing.id if existing else None
        original_components = json.dumps({
            "code_score": existing.code_score, "data_score": existing.data_score,
            "code_evaluation": existing.code_evaluation, "data_evaluation": existing.data_evaluation,
        }, sort_keys=True) if existing else None
        rubrics, signature = self._rubric_snapshot(practice)
        revision = submission.revision
        practice_input = self.practices.to_schema(practice)
        submission_input = self.submissions.to_schema(submission)
        # Release the read transaction and its connection before external IO.
        self.db.rollback()

        code_score = None
        code_evaluation = None
        data_score = None
        data_evaluation = None
        try:
            if rubrics["code"].weight > 0 and submission_input.code.strip():
                grader = self.code_grader or CodeGrader(GroqClient())
                result, code_evaluation = grader.grade(practice_input, rubrics["code"], submission_input)
                code_score = result.code_score
                if code_score is None or not 0 <= code_score <= 100:
                    raise ValueError("Invalid Code Grader score")
            if rubrics["data"].weight > 0:
                grader = self.data_grader or DataGrader(GroqClient())
                data_evaluation = grader.grade(practice_input, rubrics["data"], submission_input)
                data_score = data_evaluation.score
        except Exception as exc:
            self.db.rollback()
            raise RuntimeError("AI grading failed") from exc

        try:
            # The row lock serializes edits, invalidation, and competing grade writes.
            current, current_practice = self._context(submission_id, actor, regrade=regrade, lock=True)
            if current.status != "submitted" or current.revision != revision:
                raise GradingConflict("Submission changed during grading")
            current_practice = self.practices.get_for_update(current.practice_id)
            _, current_signature = self._rubric_snapshot(current_practice)
            if current_signature != signature:
                raise GradingConflict("Practice or Rubrics changed during grading")
            stored = self.results.get_by_submission(submission_id)
            if regrade:
                if stored is None or stored.id != original_result_id or json.dumps({
                    "code_score": stored.code_score, "data_score": stored.data_score,
                    "code_evaluation": stored.code_evaluation, "data_evaluation": stored.data_evaluation,
                }, sort_keys=True) != original_components:
                    raise GradingConflict("GradingResult changed during regrade")
                final_score = aggregate_scores({key: item.weight for key, item in rubrics.items()},
                                               {"code": code_score, "data": data_score, "vision": stored.vision_score})
                stored = self.results.replace_evaluation(
                    stored, code_score=code_score, data_score=data_score,
                    final_score=final_score, code_evaluation=code_evaluation,
                    data_evaluation=data_evaluation.model_dump(mode="json") if data_evaluation else None)
            else:
                if stored is not None and (stored.code_evaluation is not None or stored.data_evaluation is not None):
                    raise GradingConflict("Code/Data Evaluation already exists")
                final_score = aggregate_scores({key: item.weight for key, item in rubrics.items()},
                                               {"code": code_score, "data": data_score,
                                                "vision": stored.vision_score if stored else None})
                if stored is None:
                    stored = self.results.create(submission_id=submission_id, code_score=code_score,
                                                 data_score=data_score, vision_score=None, final_score=final_score,
                                                 code_evaluation=code_evaluation,
                                                 data_evaluation=data_evaluation.model_dump(mode="json") if data_evaluation else None)
                else:
                    stored = self.results.replace_evaluation(
                        stored, code_score=code_score, data_score=data_score, final_score=final_score,
                        code_evaluation=code_evaluation,
                        data_evaluation=data_evaluation.model_dump(mode="json") if data_evaluation else None)
            output = self.results.to_schema(stored)
            self.db.commit()
            return output
        except IntegrityError as exc:
            self.db.rollback()
            raise GradingConflict("Concurrent grading conflict") from exc
        except Exception:
            self.db.rollback()
            raise

    def by_submission(self, submission_id: UUID, actor) -> GradingResult:
        self._context(submission_id, actor)
        result = self.results.get_by_submission(submission_id)
        if result is None:
            raise GradingNotFound
        return self.results.to_schema(result)

    def by_id(self, result_id: UUID, actor) -> GradingResult:
        result = self.results.get_by_id(result_id)
        if result is None:
            raise GradingNotFound
        self._context(result.submission_id, actor)
        return self.results.to_schema(result)
