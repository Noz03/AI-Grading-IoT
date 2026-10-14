
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_grading_iot.models.submission import (
    Submission as SubmissionModel,
)
from ai_grading_iot.schemas.submission import (
    Submission as SubmissionSchema,
)


class SubmissionRepository:
    def __init__(self, db: Session):
        self.db = db

    # ==================================
    # CREATE
    # ==================================

    def create(
        self,
        *,
        submission: SubmissionSchema,
    ) -> SubmissionModel:

        model = SubmissionModel(
            id=submission.id,
            practice_id=submission.practice_id,
            student_id=submission.student_id,
            description=submission.description,
            code=submission.code,
            images=list(submission.images),
            status=submission.status.value,
            submitted_at=submission.submitted_at,
        )

        self.db.add(model)
        self.db.flush()

        return model

    # ==================================
    # READ
    # ==================================

    def get_by_id(
        self,
        submission_id: UUID,
    ) -> SubmissionModel | None:

        return self.db.get(
            SubmissionModel,
            submission_id,
        )

    def get_by_practice_and_student(
        self,
        *,
        practice_id: UUID,
        student_id: UUID,
    ) -> SubmissionModel | None:

        statement = select(SubmissionModel).where(
            SubmissionModel.practice_id == practice_id,
            SubmissionModel.student_id == student_id,
        )

        return self.db.scalar(statement)

    def get_by_practice(
        self,
        practice_id: UUID,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[SubmissionModel]:

        self._validate_pagination(limit, offset)

        statement = (
            select(SubmissionModel)
            .where(
                SubmissionModel.practice_id == practice_id
            )
            .order_by(
                SubmissionModel.submitted_at.desc().nullslast(),
                SubmissionModel.id,
            )
            .limit(limit)
            .offset(offset)
        )

        return list(self.db.scalars(statement).all())

    def get_by_student(
        self,
        student_id: UUID,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[SubmissionModel]:

        self._validate_pagination(limit, offset)

        statement = (
            select(SubmissionModel)
            .where(
                SubmissionModel.student_id == student_id
            )
            .order_by(
                SubmissionModel.submitted_at.desc().nullslast(),
                SubmissionModel.id,
            )
            .limit(limit)
            .offset(offset)
        )

        return list(self.db.scalars(statement).all())

    # ==================================
    # UPDATE
    # ==================================

    def update(
        self,
        model: SubmissionModel,
        *,
        submission: SubmissionSchema,
    ) -> SubmissionModel:

        if model.id != submission.id:
            raise ValueError(
                "submission.id không khớp bản ghi cần cập nhật"
            )

        if model.practice_id != submission.practice_id:
            raise ValueError(
                "Không được thay đổi Practice của Submission"
            )

        if model.student_id != submission.student_id:
            raise ValueError(
                "Không được thay đổi Student của Submission"
            )

        model.description = submission.description
        model.code = submission.code
        model.images = list(submission.images)
        model.status = submission.status.value
        model.submitted_at = submission.submitted_at

        self.db.flush()

        return model

    # ==================================
    # DELETE
    # ==================================

    def delete(
        self,
        model: SubmissionModel,
    ) -> None:

        self.db.delete(model)
        self.db.flush()

    # ==================================
    # ORM -> PYDANTIC
    # ==================================

    @staticmethod
    def to_schema(
        model: SubmissionModel,
    ) -> SubmissionSchema:

        return SubmissionSchema.model_validate(
            {
                "id": model.id,
                "practice_id": model.practice_id,
                "student_id": model.student_id,
                "description": model.description,
                "code": model.code,
                "images": model.images,
                "status": model.status,
                "submitted_at": model.submitted_at,
            }
        )

    # ==================================
    # PAGINATION
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
