from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_grading_iot.models.practice import Practice as PracticeModel
from ai_grading_iot.models.user import User
from ai_grading_iot.repositories.course_repository import CourseRepository
from ai_grading_iot.repositories.practice_repository import PracticeRepository
from ai_grading_iot.repositories.rubric_repository import RubricRepository
from ai_grading_iot.graders.rubric_generator import validate_set
from ai_grading_iot.schemas.practice import (
    Practice, PracticeMetadata, PracticeRubricReference, PracticeStatus, PracticeUpdate,
)
from ai_grading_iot.services.course_service import CourseNotFound, CourseService


class PracticeNotFound(Exception):
    pass


class PracticeConflict(Exception):
    pass


class PracticeService:
    def __init__(self, db: Session):
        self.db = db
        self.practices = PracticeRepository(db)
        self.courses = CourseService(db)
        self.rubrics = RubricRepository(db)

    def _manage_course(self, course_id: UUID, actor: User) -> None:
        if actor.role == "admin":
            self.courses.get(course_id)
        elif actor.role != "teacher" or not CourseRepository(self.db).has_membership(
            course_id, actor.id, "teacher"
        ):
            self.courses.get(course_id)
            raise PermissionError

    def _get(self, practice_id: UUID) -> PracticeModel:
        practice = self.practices.get_by_id(practice_id)
        if practice is None:
            raise PracticeNotFound
        return practice

    def _can_read(self, practice: PracticeModel, actor: User) -> None:
        if actor.role == "admin":
            return
        if actor.role == "teacher" and CourseRepository(self.db).has_membership(
            practice.course_id, actor.id, "teacher"
        ):
            return
        if actor.role == "student" and practice.status == "published" and CourseRepository(
            self.db
        ).has_membership(practice.course_id, actor.id, "student"):
            return
        raise PermissionError

    def get(self, practice_id: UUID, actor: User) -> Practice:
        practice = self._get(practice_id)
        self._can_read(practice, actor)
        return self.practices.to_schema(practice)

    def list(self, course_id: UUID, actor: User, *, limit: int, offset: int) -> list[Practice]:
        self.courses.can_access(course_id, actor)
        if actor.role == "student":
            models = self.practices.get_by_status(
                course_id, PracticeStatus.PUBLISHED, limit=limit, offset=offset
            )
        else:
            models = self.practices.get_by_course(course_id, limit=limit, offset=offset)
        return [self.practices.to_schema(model) for model in models]

    def create(self, course_id: UUID, data: Practice, actor: User) -> Practice:
        self._manage_course(course_id, actor)
        if data.status != PracticeStatus.DRAFT:
            raise PracticeConflict("New practices must be drafts")
        # The actor, not a client-supplied metadata value, identifies the creator.
        data = data.model_copy(update={
            "metadata": PracticeMetadata(created_by=str(actor.id)),
            "rubric": PracticeRubricReference(),
        })
        try:
            model = self.practices.create(course_id=course_id, practice=data)
            self.db.commit()
            return self.practices.to_schema(model)
        except IntegrityError as exc:
            self.db.rollback()
            raise PracticeConflict("Practice ID already exists") from exc
        except Exception:
            self.db.rollback()
            raise

    def update(self, practice_id: UUID, data: PracticeUpdate, actor: User) -> Practice:
        model = self.db.scalar(select(PracticeModel).where(PracticeModel.id == practice_id).with_for_update())
        if model is None:
            raise PracticeNotFound
        self._manage_course(model.course_id, actor)
        if model.status == "archived":
            raise PracticeConflict("Archived practices cannot be edited")
        changes = {name: getattr(data, name) for name in data.model_fields_set}
        if any(value is None for value in changes.values()):
            raise ValueError("Practice fields cannot be null")
        if self.practices.has_submissions(model.id):
            raise PracticeConflict("Practice has submissions")
        if model.status == "published" and set(changes) - {"title", "description"}:
            raise PracticeConflict("Published grading content cannot be edited")
        current = self.practices.to_schema(model)
        updated = current.model_copy(update=changes)
        metadata = current.metadata.model_copy(update={"updated_at": datetime.now(timezone.utc)})
        updated = updated.model_copy(update={"metadata": metadata})
        try:
            self.practices.update(model, practice=updated)
            self.db.commit()
            return self.practices.to_schema(model)
        except Exception:
            self.db.rollback()
            raise

    def change_status(self, practice_id: UUID, status: PracticeStatus, actor: User) -> Practice:
        model = self.db.scalar(select(PracticeModel).where(PracticeModel.id == practice_id).with_for_update())
        if model is None:
            raise PracticeNotFound
        self._manage_course(model.course_id, actor)
        if (model.status, status.value) not in {
            ("draft", "published"), ("published", "archived")
        }:
            raise PracticeConflict("Invalid status transition")
        if status == PracticeStatus.PUBLISHED:
            rubrics = self.rubrics.get_by_practice(model.id)
            reference = model.rubric_reference
            expected = {
                "code": reference.get("code_rubric_id"),
                "data": reference.get("dashboard_rubric_id"),
                "vision": reference.get("vision_rubric_id"),
            }
            try:
                validate_set([self.rubrics.to_schema(item) for item in rubrics])
                if any(str(item.id) != expected[item.type] for item in rubrics):
                    raise ValueError("Invalid rubric references")
            except ValueError as exc:
                raise PracticeConflict("A complete valid rubric set totaling 100% is required") from exc
        try:
            model.status = status.value
            metadata = dict(model.practice_metadata)
            metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
            model.practice_metadata = metadata
            self.db.flush()
            self.db.commit()
            return self.practices.to_schema(model)
        except Exception:
            self.db.rollback()
            raise

    def delete(self, practice_id: UUID, actor: User) -> None:
        model = self._get(practice_id)
        self._manage_course(model.course_id, actor)
        if self.practices.has_submissions(model.id):
            raise PracticeConflict("Practice has submissions")
        try:
            for rubric in self.rubrics.get_by_practice(model.id):
                self.rubrics.delete(rubric)
            self.practices.delete(model)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise PracticeConflict("Practice has dependent records") from exc
        except Exception:
            self.db.rollback()
            raise
