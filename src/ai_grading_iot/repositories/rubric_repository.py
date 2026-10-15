
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_grading_iot.models.rubric import Rubric as RubricModel
from ai_grading_iot.schemas.rubric import (
    Rubric as RubricSchema,
    RubricType,
)


class RubricRepository:
    def __init__(self, db: Session):
        self.db = db

    # ==================================
    # CREATE
    # ==================================

    def create(
        self,
        *,
        practice_id: UUID,
        rubric: RubricSchema,
    ) -> RubricModel:

        model = RubricModel(
            id=rubric.id,
            practice_id=practice_id,
            type=rubric.type.value,
            weight=rubric.weight,
            criteria=list(rubric.criteria),
        )

        self.db.add(model)
        self.db.flush()

        return model

    # ==================================
    # READ
    # ==================================

    def get_by_id(
        self,
        rubric_id: UUID,
    ) -> RubricModel | None:
        return self.db.get(RubricModel, rubric_id)

    def get_by_practice(
        self,
        practice_id: UUID,
    ) -> list[RubricModel]:

        statement = (
            select(RubricModel)
            .where(RubricModel.practice_id == practice_id)
            .order_by(RubricModel.type, RubricModel.id)
            .execution_options(populate_existing=True)
        )

        return list(self.db.scalars(statement).all())

    def get_by_type(
        self,
        practice_id: UUID,
        rubric_type: RubricType,
    ) -> RubricModel | None:

        statement = select(RubricModel).where(
            RubricModel.practice_id == practice_id,
            RubricModel.type == rubric_type.value,
        )

        return self.db.scalar(statement)

    # ==================================
    # UPDATE
    # ==================================

    def update(
        self,
        model: RubricModel,
        *,
        rubric: RubricSchema,
    ) -> RubricModel:

        if model.id != rubric.id:
            raise ValueError(
                "rubric.id không khớp với bản ghi cần cập nhật"
            )

        if model.type != rubric.type.value:
            raise ValueError(
                "Không được thay đổi loại Rubric"
            )

        model.weight = rubric.weight
        model.criteria = list(rubric.criteria)

        self.db.flush()

        return model

    # ==================================
    # DELETE
    # ==================================

    def delete(
        self,
        model: RubricModel,
    ) -> None:
        self.db.delete(model)
        self.db.flush()

    # ==================================
    # ORM -> PYDANTIC
    # ==================================

    @staticmethod
    def to_schema(
        model: RubricModel,
    ) -> RubricSchema:

        return RubricSchema.model_validate(
            {
                "id": model.id,
                "type": model.type,
                "weight": model.weight,
                "criteria": model.criteria,
            }
        )
