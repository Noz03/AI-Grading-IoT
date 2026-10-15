"""Submission lifecycle, authorization and transaction coordination."""

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_grading_iot.models.user import User
from ai_grading_iot.repositories.course_repository import CourseRepository
from ai_grading_iot.repositories.grading_repository import GradingRepository
from ai_grading_iot.repositories.practice_repository import PracticeRepository
from ai_grading_iot.repositories.submission_repository import SubmissionRepository
from ai_grading_iot.schemas.submission import Submission, SubmissionCreate, SubmissionUpdate
from ai_grading_iot.services.image_storage_service import ImageStorageService

logger = logging.getLogger(__name__)


class SubmissionNotFound(Exception):
    pass


class SubmissionConflict(Exception):
    pass


class SubmissionService:
    def __init__(self, db: Session, storage: ImageStorageService | None = None):
        self.db = db
        self.submissions = SubmissionRepository(db)
        self.practices = PracticeRepository(db)
        self.courses = CourseRepository(db)
        self.grading = GradingRepository(db)
        self.storage = storage or ImageStorageService()

    def _practice(self, practice_id: UUID):
        practice = self.practices.get_by_id(practice_id)
        if practice is None:
            raise SubmissionNotFound
        return practice

    def _write_allowed(self, practice, actor: User) -> None:
        if actor.role != "student" or not self.courses.has_membership(
            practice.course_id, actor.id, "student"
        ):
            raise PermissionError
        if practice.status != "published":
            raise SubmissionConflict("Practice is not published")

    def _read_allowed(self, model, practice, actor: User) -> None:
        if actor.role == "admin":
            return
        if actor.role == "teacher" and self.courses.has_membership(
            practice.course_id, actor.id, "teacher"
        ):
            return
        if actor.role == "student" and model.student_id == actor.id and self.courses.has_membership(
            practice.course_id, actor.id, "student"
        ):
            return
        raise PermissionError

    def _get(self, submission_id: UUID, *, lock: bool = False):
        model = (self.submissions.get_for_update(submission_id) if lock
                 else self.submissions.get_by_id(submission_id))
        if model is None:
            raise SubmissionNotFound
        return model

    def _owner(self, model, actor: User):
        if actor.role != "student" or model.student_id != actor.id:
            raise PermissionError
        self._write_allowed(self._practice(model.practice_id), actor)

    def _changed(self, model):
        model.revision += 1
        if model.status == "submitted":
            model.status = "draft"
            model.submitted_at = None
            result = self.grading.get_by_submission(model.id)
            if result is not None:
                self.grading.delete(result)

    def create(self, practice_id: UUID, data: SubmissionCreate, actor: User) -> Submission:
        self._write_allowed(self._practice(practice_id), actor)
        if self.submissions.get_by_practice_and_student(practice_id=practice_id, student_id=actor.id):
            raise SubmissionConflict("Submission already exists")
        try:
            model = self.submissions.create(submission=Submission(
                practice_id=practice_id, student_id=actor.id,
                description=data.description, code=data.code,
            ))
            self.db.commit()
            return self.submissions.to_schema(model)
        except IntegrityError as exc:
            self.db.rollback()
            raise SubmissionConflict("Submission already exists") from exc
        except Exception:
            self.db.rollback()
            raise

    def mine(self, actor: User, *, limit: int, offset: int) -> list[Submission]:
        if actor.role != "student":
            raise PermissionError
        return [self.submissions.to_schema(item) for item in
                self.submissions.get_by_student_with_enrollment(actor.id, limit=limit, offset=offset)]

    def for_practice(self, practice_id: UUID, actor: User, *, limit: int, offset: int) -> list[Submission]:
        practice = self._practice(practice_id)
        if actor.role != "admin" and not (actor.role == "teacher" and self.courses.has_membership(
            practice.course_id, actor.id, "teacher"
        )):
            raise PermissionError
        return [self.submissions.to_schema(item) for item in self.submissions.get_by_practice(
            practice_id, limit=limit, offset=offset
        )]

    def get(self, submission_id: UUID, actor: User) -> Submission:
        model = self._get(submission_id)
        self._read_allowed(model, self._practice(model.practice_id), actor)
        return self.submissions.to_schema(model)

    def update(self, submission_id: UUID, data: SubmissionUpdate, actor: User) -> Submission:
        model = self._get(submission_id, lock=True)
        self._owner(model, actor)
        changes = data.model_dump(exclude_unset=True)
        if any(value is None for name, value in changes.items() if name != "data_evidence"):
            raise ValueError("Submission content cannot be null")
        if "data_evidence" in changes:
            evidence = data.data_evidence
            changes["data_evidence"] = evidence.model_dump(mode="json") if evidence else None
            if evidence and evidence.dashboard:
                for image_id in evidence.dashboard.image_ids:
                    self.storage.read(self._image_reference(model, image_id))
        if not any(getattr(model, name) != value for name, value in changes.items()):
            return self.submissions.to_schema(model)
        try:
            self._changed(model)
            for name, value in changes.items():
                setattr(model, name, value)
            self.db.flush()
            self.db.commit()
            return self.submissions.to_schema(model)
        except Exception:
            self.db.rollback()
            raise

    def submit(self, submission_id: UUID, actor: User) -> Submission:
        model = self._get(submission_id, lock=True)
        self._owner(model, actor)
        if model.status != "draft":
            raise SubmissionConflict("Submission is already submitted")
        if not (model.code.strip() or model.description.strip() or model.images or model.data_evidence):
            raise ValueError("Submission must contain code, description or images")
        try:
            model.status = "submitted"
            model.submitted_at = datetime.now(timezone.utc)
            self.db.flush()
            self.db.commit()
            return self.submissions.to_schema(model)
        except Exception:
            self.db.rollback()
            raise

    def _image_reference(self, model, image_id: UUID) -> str:
        prefix = f"submissions/{model.id}/{image_id}."
        matches = [reference for reference in model.images if reference.startswith(prefix)]
        if len(matches) != 1:
            raise SubmissionNotFound
        # Validate old database references before touching storage.
        self.storage.path(matches[0])
        return matches[0]

    def upload(self, submission_id: UUID, upload: UploadFile, actor: User):
        model = self._get(submission_id, lock=True)
        self._owner(model, actor)
        if len(model.images) >= 5:
            raise SubmissionConflict("Maximum five images")
        payload, extension, media_type = self.storage.validate(upload)
        image_id = uuid4()
        reference = self.storage.reference(model.id, image_id, extension)
        stored = False
        try:
            self.storage.store(reference, payload)
            stored = True
            model.images = [*model.images, reference]
            self._changed(model)
            self.db.flush()
            self.db.commit()
        except Exception:
            self.db.rollback()
            if stored:
                try:
                    self.storage.remove(reference)
                except OSError:
                    logger.exception("Failed to clean up image after database rollback")
            raise
        return image_id, extension, media_type

    def read_image(self, submission_id: UUID, image_id: UUID, actor: User):
        model = self._get(submission_id)
        self._read_allowed(model, self._practice(model.practice_id), actor)
        reference = self._image_reference(model, image_id)
        content_type = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}[reference.rsplit(".", 1)[1]]
        return self.storage.read(reference), content_type

    def delete_image(self, submission_id: UUID, image_id: UUID, actor: User) -> None:
        model = self._get(submission_id, lock=True)
        self._owner(model, actor)
        reference = self._image_reference(model, image_id)
        try:
            model.images = [item for item in model.images if item != reference]
            if model.data_evidence and model.data_evidence.get("dashboard"):
                evidence = dict(model.data_evidence)
                dashboard = dict(evidence["dashboard"])
                dashboard["image_ids"] = [item for item in dashboard.get("image_ids", []) if item != str(image_id)]
                evidence["dashboard"] = dashboard
                model.data_evidence = evidence
            self._changed(model)
            self.db.flush()
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        try:
            self.storage.remove(reference)
        except OSError:
            logger.exception("Image cleanup failed after database commit: %s", image_id)
