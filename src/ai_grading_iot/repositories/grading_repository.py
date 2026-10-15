
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_grading_iot.models.grading_result import (
    GradingResult as GradingResultModel,
)
from ai_grading_iot.schemas.grading_result import (
    GradingResult as GradingResultSchema,
)
from ai_grading_iot.schemas.code_evaluation import (
    CodeEvaluation,
)


class GradingRepository:
    def __init__(self, db: Session):
        self.db = db

    # ==================================
    # CREATE
    # ==================================

    def create(
        self,
        *,
        submission_id: UUID,
        code_score: float | None = None,
        data_score: float | None = None,
        vision_score: float | None = None,
        final_score: float | None = None,
        code_evaluation: CodeEvaluation | None = None,
        data_evaluation: dict | None = None,
        vision_evaluation: dict | None = None,
    ) -> GradingResultModel:

        model = GradingResultModel(
            submission_id=submission_id,
            code_score=code_score,
            data_score=data_score,
            vision_score=vision_score,
            final_score=final_score,
            code_evaluation=(
                code_evaluation.model_dump(mode="json")
                if code_evaluation is not None
                else None
            ),
            data_evaluation=data_evaluation,
            vision_evaluation=vision_evaluation,
            graded_at=datetime.now(timezone.utc),
        )

        self.db.add(model)
        self.db.flush()

        return model

    # ==================================
    # READ
    # ==================================

    def get_by_id(
        self,
        grading_id: UUID,
    ) -> GradingResultModel | None:

        return self.db.get(
            GradingResultModel,
            grading_id,
        )

    def get_by_submission(
        self,
        submission_id: UUID,
    ) -> GradingResultModel | None:

        statement = select(GradingResultModel).where(
            GradingResultModel.submission_id == submission_id
        )

        return self.db.scalar(statement)

    # ==================================
    # UPDATE
    # ==================================

    def update(
        self,
        model: GradingResultModel,
        *,
        code_score: float | None = None,
        data_score: float | None = None,
        vision_score: float | None = None,
        final_score: float | None = None,
        code_evaluation: CodeEvaluation | None = None,
    ) -> GradingResultModel:

        # None ở đây nghĩa là không cập nhật trường đó.
        if code_score is not None:
            model.code_score = code_score

        if data_score is not None:
            model.data_score = data_score

        if vision_score is not None:
            model.vision_score = vision_score

        if final_score is not None:
            model.final_score = final_score

        if code_evaluation is not None:
            model.code_evaluation = (
                code_evaluation.model_dump(mode="json")
            )

        model.graded_at = datetime.now(timezone.utc)

        self.db.flush()

        return model

    # ==================================
    # SAVE OR UPDATE
    # ==================================

    def replace_evaluation(self, model: GradingResultModel, *,
                           code_score: float | None, data_score: float | None,
                           final_score: float | None,
                           code_evaluation: CodeEvaluation | None,
                           data_evaluation: dict | None) -> GradingResultModel:
        """Atomic regrade replacement; unlike update(), None clears an old score."""
        model.code_score = code_score
        model.data_score = data_score
        # A Code/Data regrade only replaces those components.
        model.final_score = final_score
        model.code_evaluation = code_evaluation.model_dump(mode="json") if code_evaluation else None
        model.data_evaluation = data_evaluation
        model.graded_at = datetime.now(timezone.utc)
        self.db.flush()
        return model

    def save_or_update(
        self,
        *,
        submission_id: UUID,
        code_score: float | None = None,
        data_score: float | None = None,
        vision_score: float | None = None,
        final_score: float | None = None,
        code_evaluation: CodeEvaluation | None = None,
    ) -> GradingResultModel:

        existing = self.get_by_submission(submission_id)

        if existing is None:
            return self.create(
                submission_id=submission_id,
                code_score=code_score,
                data_score=data_score,
                vision_score=vision_score,
                final_score=final_score,
                code_evaluation=code_evaluation,
            )

        return self.update(
            existing,
            code_score=code_score,
            data_score=data_score,
            vision_score=vision_score,
            final_score=final_score,
            code_evaluation=code_evaluation,
        )

    # ==================================
    # DELETE
    # ==================================

    def delete(
        self,
        model: GradingResultModel,
    ) -> None:

        self.db.delete(model)
        self.db.flush()

    # ==================================
    # ORM -> PYDANTIC
    # ==================================

    @staticmethod
    def to_schema(
        model: GradingResultModel,
    ) -> GradingResultSchema:

        return GradingResultSchema.model_validate(
            {
                "id": model.id,
                "submission_id": model.submission_id,
                "code_score": model.code_score,
                "data_score": model.data_score,
                "vision_score": model.vision_score,
                "final_score": model.final_score,
                "code_evaluation": model.code_evaluation,
                "data_evaluation": model.data_evaluation,
                "vision_evaluation": model.vision_evaluation,
                "graded_at": model.graded_at,
                "status": ("insufficient_evidence" if any(item and item.get("evidence_status") == "insufficient"
                           for item in (model.data_evaluation, model.vision_evaluation)) else
                           "complete" if model.final_score is not None else "partial"),
            }
        )

    # ==================================
    # JSONB -> CODE EVALUATION
    # ==================================

    @staticmethod
    def get_code_evaluation(
        model: GradingResultModel,
    ) -> CodeEvaluation | None:

        if model.code_evaluation is None:
            return None

        return CodeEvaluation.model_validate(
            model.code_evaluation
        )
