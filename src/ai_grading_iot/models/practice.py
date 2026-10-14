from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import (
    JSONB,
    UUID as PG_UUID,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_grading_iot.db.base import Base


class Practice(Base):
    __tablename__ = "practices"

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_practices_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    course_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("courses.id"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    requirements: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    environment: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    hardware: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )

    rubric_reference: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    version: Mapped[str] = mapped_column(
        String(20),
        default="1.0",
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="draft",
        nullable=False,
    )

    practice_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
    )

    course = relationship(
        "Course",
        back_populates="practices",
    )

    rubrics = relationship(
        "Rubric",
        back_populates="practice",
    )

    submissions = relationship(
        "Submission",
        back_populates="practice",
    )
