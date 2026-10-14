from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_grading_iot.db.base import Base


class CourseTeacher(Base):
    __tablename__ = "course_teachers"

    course_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("courses.id"),
        primary_key=True,
    )

    teacher_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        primary_key=True,
    )

    course = relationship(
        "Course",
        back_populates="teaching_assignments",
    )

    teacher = relationship(
        "User",
        back_populates="teaching_assignments",
    )
