from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import (
    JSONB,
    UUID as PG_UUID,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_grading_iot.db.base import Base

from sqlalchemy import UniqueConstraint

class Rubric(Base):
    __tablename__ = "rubrics"

    __table_args__ = (
    CheckConstraint(
        "type IN ('code', 'data', 'vision')",
        name="ck_rubrics_type",
    ),
    CheckConstraint(
        "weight >= 0 AND weight <= 100",
        name="ck_rubrics_weight",
    ),
    UniqueConstraint(
        "practice_id",
        "type",
        name="uq_rubric_practice_type",
    ),
)

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    practice_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("practices.id"),
        nullable=False,
        index=True,
    )

    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    weight: Mapped[float] = mapped_column(
        Numeric(5, 2, asdecimal=False),
        nullable=False,
    )

    criteria: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
    )

    practice = relationship(
        "Practice",
        back_populates="rubrics",
    )
