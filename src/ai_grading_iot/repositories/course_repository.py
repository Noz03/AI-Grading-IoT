
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_grading_iot.models.course import Course
from ai_grading_iot.models.course_teacher import CourseTeacher
from ai_grading_iot.models.course_enrollment import CourseEnrollment
from ai_grading_iot.models.user import User


class CourseRepository:
    def __init__(self, db: Session):
        self.db = db

    # ==============================
    # COURSE CRUD
    # ==============================

    def create(
        self,
        *,
        code: str,
        name: str,
        description: str | None = None,
    ) -> Course:
        course = Course(
            code=code,
            name=name,
            description=description,
        )

        self.db.add(course)
        self.db.flush()

        return course

    def get_by_id(self, course_id: UUID) -> Course | None:
        return self.db.get(Course, course_id)

    def get_by_code(self, code: str) -> Course | None:
        statement = select(Course).where(
            Course.code == code
        )

        return self.db.scalar(statement)

    def get_all(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Course]:
        if not 1 <= limit <= 100:
            raise ValueError("limit phải nằm trong khoảng 1–100")

        if offset < 0:
            raise ValueError("offset không được âm")

        statement = (
            select(Course)
            .order_by(Course.code, Course.id)
            .limit(limit)
            .offset(offset)
        )

        return list(self.db.scalars(statement).all())

    def has_membership(self, course_id: UUID, user_id: UUID, role: str) -> bool:
        model = CourseTeacher if role == "teacher" else CourseEnrollment
        field = model.teacher_id if role == "teacher" else model.student_id
        return self.db.scalar(
            select(model.course_id).where(model.course_id == course_id, field == user_id)
        ) is not None

    def get_for_user(
        self, user_id: UUID, role: str, *, limit: int = 20, offset: int = 0
    ) -> list[Course]:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("Invalid pagination")
        model = CourseTeacher if role == "teacher" else CourseEnrollment
        field = model.teacher_id if role == "teacher" else model.student_id
        statement = (
            select(Course).join(model, model.course_id == Course.id)
            .where(field == user_id).order_by(Course.code, Course.id)
            .limit(limit).offset(offset)
        )
        return list(self.db.scalars(statement).all())

    def update(
        self,
        course: Course,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Course:
        if name is not None:
            course.name = name

        if description is not None:
            course.description = description

        self.db.flush()

        return course

    def delete(self, course: Course) -> None:
        self.db.delete(course)
        self.db.flush()

    # ==============================
    # TEACHER MANAGEMENT
    # ==============================

    def assign_teacher(
        self,
        *,
        course_id: UUID,
        teacher_id: UUID,
    ) -> CourseTeacher:
        assignment = CourseTeacher(
            course_id=course_id,
            teacher_id=teacher_id,
        )

        self.db.add(assignment)
        self.db.flush()

        return assignment

    def remove_teacher(
        self,
        *,
        course_id: UUID,
        teacher_id: UUID,
    ) -> bool:
        assignment = self.db.get(
            CourseTeacher,
            (course_id, teacher_id),
        )

        if assignment is None:
            return False

        self.db.delete(assignment)
        self.db.flush()

        return True

    def get_teachers(self, course_id: UUID) -> list[User]:
        statement = (
            select(User)
            .join(
                CourseTeacher,
                CourseTeacher.teacher_id == User.id,
            )
            .where(CourseTeacher.course_id == course_id)
            .order_by(User.full_name, User.id)
        )

        return list(self.db.scalars(statement).all())

    # ==============================
    # STUDENT MANAGEMENT
    # ==============================

    def enroll_student(
        self,
        *,
        course_id: UUID,
        student_id: UUID,
    ) -> CourseEnrollment:
        enrollment = CourseEnrollment(
            course_id=course_id,
            student_id=student_id,
        )

        self.db.add(enrollment)
        self.db.flush()

        return enrollment

    def remove_student(
        self,
        *,
        course_id: UUID,
        student_id: UUID,
    ) -> bool:
        enrollment = self.db.get(
            CourseEnrollment,
            (course_id, student_id),
        )

        if enrollment is None:
            return False

        self.db.delete(enrollment)
        self.db.flush()

        return True

    def get_students(self, course_id: UUID) -> list[User]:
        statement = (
            select(User)
            .join(
                CourseEnrollment,
                CourseEnrollment.student_id == User.id,
            )
            .where(CourseEnrollment.course_id == course_id)
            .order_by(User.full_name, User.id)
        )

        return list(self.db.scalars(statement).all())
