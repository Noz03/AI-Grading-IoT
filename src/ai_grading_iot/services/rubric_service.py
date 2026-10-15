from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_grading_iot.graders.rubric_generator import RubricGenerator, RubricGenerationError
from ai_grading_iot.models.practice import Practice as PracticeModel
from ai_grading_iot.models.user import User
from ai_grading_iot.repositories.practice_repository import PracticeRepository
from ai_grading_iot.repositories.rubric_repository import RubricRepository
from ai_grading_iot.schemas.rubric import Rubric, RubricDetail, RubricUpdate
from ai_grading_iot.services.practice_service import PracticeConflict, PracticeService


class RubricNotFound(Exception):
    pass


class RubricConflict(Exception):
    pass


class RubricPersistenceError(Exception):
    pass


class RubricService:
    def __init__(self, db: Session, generator: RubricGenerator | None = None):
        self.db = db
        self.practices = PracticeRepository(db)
        self.rubrics = RubricRepository(db)
        self.generator = generator or RubricGenerator()

    def _practice(self, practice_id: UUID) -> PracticeModel:
        return PracticeService(self.db)._get(practice_id)

    def _editable(self, practice: PracticeModel, actor: User) -> None:
        PracticeService(self.db)._manage_course(practice.course_id, actor)
        if practice.status != "draft" or self.practices.has_submissions(practice.id):
            raise RubricConflict("Only draft practices without submissions can change rubrics")

    def _detail(self, model) -> RubricDetail:
        return RubricDetail.model_validate({
            **self.rubrics.to_schema(model).model_dump(), "practice_id": model.practice_id
        })

    def list(self, practice_id: UUID, actor: User) -> list[RubricDetail]:
        practice = self._practice(practice_id)
        PracticeService(self.db)._can_read(practice, actor)
        return [self._detail(item) for item in self.rubrics.get_by_practice(practice_id)]

    def get(self, rubric_id: UUID, actor: User) -> RubricDetail:
        item = self.rubrics.get_by_id(rubric_id)
        if item is None:
            raise RubricNotFound
        PracticeService(self.db)._can_read(self._practice(item.practice_id), actor)
        return self._detail(item)

    def update(self, rubric_id: UUID, data: RubricUpdate, actor: User) -> RubricDetail:
        try:
            item = self.rubrics.get_by_id(rubric_id)
            if item is None:
                raise RubricNotFound
            practice = self.db.scalar(select(PracticeModel).where(
                PracticeModel.id == item.practice_id).with_for_update())
            self._editable(practice, actor)
            changes = data.model_dump(exclude_unset=True)
            if not changes or any(value is None for value in changes.values()):
                raise ValueError("Provide non-null weight or criteria")
            revised = Rubric.model_validate({**self.rubrics.to_schema(item).model_dump(), **changes})
            self.rubrics.update(item, rubric=revised)
            self.db.commit()
            return self._detail(item)
        except (RubricNotFound, RubricConflict, PermissionError, ValueError):
            self.db.rollback()
            raise
        except Exception as exc:
            self.db.rollback()
            raise RubricPersistenceError("Rubric persistence failed; retry is available") from exc

    def generate(self, practice_id: UUID, actor: User, *, replace: bool = False) -> list[RubricDetail]:
        practice = self._practice(practice_id)
        self._editable(practice, actor)
        existing = self.rubrics.get_by_practice(practice_id)
        if existing and not replace:
            raise RubricConflict("Rubrics already exist; use explicit regeneration")
        rubric_snapshot = [
            (item.id, item.type, item.weight, tuple(item.criteria)) for item in existing
        ]
        reference_snapshot = dict(practice.rubric_reference)
        snapshot = self.practices.to_schema(practice)
        signature = snapshot.model_dump_json(include={
            "title", "description", "requirements", "environment", "hardware", "version"
        })
        # Release the read transaction and its connection before the external request.
        self.db.rollback()
        proposals = self.generator.generate(snapshot)
        try:
            practice = self.db.scalar(select(PracticeModel).where(
                PracticeModel.id == practice_id).with_for_update())
            if practice is None:
                raise RubricConflict("Practice changed during generation")
            self._editable(practice, actor)
            current = self.practices.to_schema(practice).model_dump_json(include={
                "title", "description", "requirements", "environment", "hardware", "version"
            })
            if current != signature:
                raise RubricConflict("Practice changed during generation; retry")
            existing = self.rubrics.get_by_practice(practice_id)
            if [
                (item.id, item.type, item.weight, tuple(item.criteria)) for item in existing
            ] != rubric_snapshot or practice.rubric_reference != reference_snapshot:
                raise RubricConflict("Rubrics changed during generation; retry")
            if existing and not replace:
                raise RubricConflict("Rubrics changed during generation; use regeneration")
            by_type = {item.type: item for item in existing}
            for proposal in proposals:
                current_item = by_type.get(proposal.type.value)
                if current_item is None:
                    by_type[proposal.type.value] = self.rubrics.create(
                        practice_id=practice_id, rubric=proposal)
                else:
                    revised = proposal.model_copy(update={"id": current_item.id})
                    self.rubrics.update(current_item, rubric=revised)
            practice.rubric_reference = {
                "code_rubric_id": str(by_type["code"].id),
                "dashboard_rubric_id": str(by_type["data"].id),
                "vision_rubric_id": str(by_type["vision"].id),
            }
            self.db.flush()
            self.db.commit()
            return [self._detail(item) for item in self.rubrics.get_by_practice(practice_id)]
        except IntegrityError as exc:
            self.db.rollback()
            raise RubricConflict("Concurrent rubric change; retry") from exc
        except (RubricConflict, PermissionError):
            self.db.rollback()
            raise
        except Exception as exc:
            self.db.rollback()
            raise RubricPersistenceError("Rubric persistence failed; retry is available") from exc
