from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import (
    JSONB,
    UUID as PG_UUID,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_grading_iot.db.base import Base


class GradingResult(Base):
    __tablename__ = "grading_results"

    __table_args__ = (
        UniqueConstraint(
            "submission_id",
            name="uq_grading_result_submission",
        ),
        CheckConstraint(
            "code_score BETWEEN 0 AND 100",
            name="ck_grading_code_score",
        ),
        CheckConstraint(
            "data_score BETWEEN 0 AND 100",
            name="ck_grading_data_score",
        ),
        CheckConstraint(
            "vision_score BETWEEN 0 AND 100",
            name="ck_grading_vision_score",
        ),
        CheckConstraint(
            "final_score BETWEEN 0 AND 100",
            name="ck_grading_final_score",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    submission_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("submissions.id"),
        nullable=False,
    )

    code_score: Mapped[float | None] = mapped_column(
        Numeric(5, 2, asdecimal=False),
        nullable=True,
    )

    data_score: Mapped[float | None] = mapped_column(
        Numeric(5, 2, asdecimal=False),
        nullable=True,
    )

    vision_score: Mapped[float | None] = mapped_column(
        Numeric(5, 2, asdecimal=False),
        nullable=True,
    )

    final_score: Mapped[float | None] = mapped_column(
        Numeric(5, 2, asdecimal=False),
        nullable=True,
    )

    code_evaluation: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    graded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    submission = relationship(
        "Submission",
        back_populates="grading_result",
    )
