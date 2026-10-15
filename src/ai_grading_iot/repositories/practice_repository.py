
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_grading_iot.models.practice import Practice as PracticeModel
from ai_grading_iot.models.submission import Submission
from ai_grading_iot.schemas.practice import (
    Practice as PracticeSchema,
    PracticeStatus,
)


class PracticeRepository:
    def __init__(self, db: Session):
        self.db = db

    # ==================================
    # CREATE
    # ==================================

    def create(
        self,
        *,
        course_id: UUID,
        practice: PracticeSchema,
    ) -> PracticeModel:

        model = PracticeModel(
            id=practice.practice_id,
            course_id=course_id,
            title=practice.title,
            description=practice.description,
            requirements=practice.requirements.model_dump(
                mode="json"
            ),
            environment=practice.environment.model_dump(
                mode="json"
            ),
            hardware=[
                item.model_dump(mode="json")
                for item in practice.hardware
            ],
            rubric_reference=practice.rubric.model_dump(
                mode="json"
            ),
            version=practice.version,
            status=practice.status.value,
            practice_metadata=practice.metadata.model_dump(
                mode="json"
            ),
        )

        self.db.add(model)
        self.db.flush()

        return model

    # ==================================
    # READ
    # ==================================

    def get_by_id(
        self,
        practice_id: UUID,
    ) -> PracticeModel | None:

        return self.db.get(
            PracticeModel,
            practice_id,
        )

    def get_for_update(self, practice_id: UUID) -> PracticeModel | None:
        return self.db.scalar(
            select(PracticeModel).where(PracticeModel.id == practice_id)
            .with_for_update().execution_options(populate_existing=True)
        )

    def has_any(self, course_id: UUID) -> bool:
        return self.db.scalar(
            select(PracticeModel.id).where(PracticeModel.course_id == course_id).limit(1)
        ) is not None

    def has_submissions(self, practice_id: UUID) -> bool:
        return self.db.scalar(
            select(Submission.id).where(Submission.practice_id == practice_id).limit(1)
        ) is not None

    def get_by_course(
        self,
        course_id: UUID,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[PracticeModel]:

        self._validate_pagination(limit, offset)

        statement = (
            select(PracticeModel)
            .where(PracticeModel.course_id == course_id)
            .order_by(
                PracticeModel.title,
                PracticeModel.id,
            )
            .limit(limit)
            .offset(offset)
        )

        return list(
            self.db.scalars(statement).all()
        )

    def get_by_status(
        self,
        course_id: UUID,
        status: PracticeStatus,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[PracticeModel]:

        self._validate_pagination(limit, offset)

        statement = (
            select(PracticeModel)
            .where(
                PracticeModel.course_id == course_id,
                PracticeModel.status == status.value,
            )
            .order_by(
                PracticeModel.title,
                PracticeModel.id,
            )
            .limit(limit)
            .offset(offset)
        )

        return list(
            self.db.scalars(statement).all()
        )

    # ==================================
    # UPDATE
    # ==================================

    def update(
        self,
        model: PracticeModel,
        *,
        practice: PracticeSchema,
    ) -> PracticeModel:

        if model.id != practice.practice_id:
            raise ValueError(
                "practice_id không khớp với bản ghi cần cập nhật"
            )

        model.title = practice.title
        model.description = practice.description

        model.requirements = (
            practice.requirements.model_dump(mode="json")
        )

        model.environment = (
            practice.environment.model_dump(mode="json")
        )

        model.hardware = [
            item.model_dump(mode="json")
            for item in practice.hardware
        ]

        model.rubric_reference = (
            practice.rubric.model_dump(mode="json")
        )

        model.version = practice.version
        model.status = practice.status.value

        model.practice_metadata = (
            practice.metadata.model_dump(mode="json")
        )

        self.db.flush()

        return model

    # ==================================
    # DELETE
    # ==================================

    def delete(
        self,
        model: PracticeModel,
    ) -> None:

        self.db.delete(model)
        self.db.flush()

    # ==================================
    # ORM -> PYDANTIC SCHEMA
    # ==================================

    @staticmethod
    def to_schema(
        model: PracticeModel,
    ) -> PracticeSchema:

        return PracticeSchema.model_validate(
            {
                "practice_id": model.id,
                "title": model.title,
                "description": model.description,
                "requirements": model.requirements,
                "environment": model.environment,
                "hardware": model.hardware,
                "rubric": model.rubric_reference,
                "version": model.version,
                "status": model.status,
                "metadata": model.practice_metadata,
            }
        )

    # ==================================
    # HELPERS
    # ==================================

    @staticmethod
    def _validate_pagination(
        limit: int,
        offset: int,
    ) -> None:

        if not 1 <= limit <= 100:
            raise ValueError(
                "limit phải nằm trong khoảng 1–100"
            )

        if offset < 0:
            raise ValueError(
                "offset không được âm"
            )
