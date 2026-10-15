from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_grading_iot.models.course import Course
from ai_grading_iot.models.user import User
from ai_grading_iot.repositories.course_repository import CourseRepository
from ai_grading_iot.repositories.practice_repository import PracticeRepository
from ai_grading_iot.repositories.user_repository import UserRepository
from ai_grading_iot.schemas.course import CourseCreate, CourseUpdate


class CourseNotFound(Exception):
    pass


class CourseConflict(Exception):
    pass


class InvalidMember(Exception):
    pass


class CourseService:
    def __init__(self, db: Session):
        self.db = db
        self.courses = CourseRepository(db)
        self.users = UserRepository(db)

    def get(self, course_id: UUID) -> Course:
        course = self.courses.get_by_id(course_id)
        if course is None:
            raise CourseNotFound
        return course

    def list_for(self, actor: User, *, limit: int, offset: int) -> list[Course]:
        if actor.role == "admin":
            return self.courses.get_all(limit=limit, offset=offset)
        return self.courses.get_for_user(actor.id, actor.role, limit=limit, offset=offset)

    def can_access(self, course_id: UUID, actor: User) -> Course:
        course = self.get(course_id)
        if actor.role != "admin" and not self.courses.has_membership(course_id, actor.id, actor.role):
            raise PermissionError
        return course

    def create(self, data: CourseCreate) -> Course:
        if self.courses.get_by_code(data.code):
            raise CourseConflict("Course code already exists")
        try:
            course = self.courses.create(**data.model_dump())
            self.db.commit()
            return course
        except IntegrityError as exc:
            self.db.rollback()
            raise CourseConflict("Course code already exists") from exc
        except Exception:
            self.db.rollback()
            raise

    def update(self, course_id: UUID, data: CourseUpdate) -> Course:
        try:
            course = self.get(course_id)
            changes = data.model_dump(exclude_unset=True)
            if "name" in changes and changes["name"] is None:
                raise ValueError("Course name cannot be null")
            if "description" in changes:
                course.description = changes.pop("description")
            course = self.courses.update(course, **changes)
            self.db.commit()
            return course
        except Exception:
            self.db.rollback()
            raise

    def delete(self, course_id: UUID) -> None:
        try:
            course = self.get(course_id)
            if PracticeRepository(self.db).has_any(course_id):
                raise CourseConflict("Course has practices; academic history must be preserved")
            # Assignments and enrollments are removed explicitly before deleting the course.
            for teacher in self.courses.get_teachers(course_id):
                self.courses.remove_teacher(course_id=course_id, teacher_id=teacher.id)
            for student in self.courses.get_students(course_id):
                self.courses.remove_student(course_id=course_id, student_id=student.id)
            self.courses.delete(course)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise CourseConflict("Course has dependent records") from exc
        except Exception:
            self.db.rollback()
            raise

    def assign_teacher(self, course_id: UUID, teacher_id: UUID) -> None:
        self.get(course_id)
        teacher = self.users.get_by_id(teacher_id)
        if teacher is None:
            raise CourseNotFound("User not found")
        if teacher.role != "teacher" or not teacher.is_active:
            raise InvalidMember("An active teacher is required")
        if self.courses.has_membership(course_id, teacher_id, "teacher"):
            raise CourseConflict("Teacher already assigned")
        try:
            self.courses.assign_teacher(course_id=course_id, teacher_id=teacher_id)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise CourseConflict("Teacher already assigned") from exc
        except Exception:
            self.db.rollback()
            raise

    def remove_teacher(self, course_id: UUID, teacher_id: UUID) -> None:
        self.get(course_id)
        try:
            if not self.courses.remove_teacher(course_id=course_id, teacher_id=teacher_id):
                raise CourseNotFound("Teacher assignment not found")
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def join(self, code: str, student: User) -> Course:
        course = self.courses.get_by_code(code)
        if course is None:
            raise CourseNotFound
        if self.courses.has_membership(course.id, student.id, "student"):
            raise CourseConflict("Student already enrolled")
        try:
            self.courses.enroll_student(course_id=course.id, student_id=student.id)
            self.db.commit()
            return course
        except IntegrityError as exc:
            self.db.rollback()
            raise CourseConflict("Student already enrolled") from exc
        except Exception:
            self.db.rollback()
            raise

    def add_student(self, course_id: UUID, student_id: UUID) -> None:
        self.get(course_id)
        student = self.users.get_by_id(student_id)
        if student is None:
            raise CourseNotFound("User not found")
        if student.role != "student" or not student.is_active:
            raise InvalidMember("An active student is required")
        if self.courses.has_membership(course_id, student_id, "student"):
            raise CourseConflict("Student already enrolled")
        try:
            self.courses.enroll_student(course_id=course_id, student_id=student_id)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise CourseConflict("Student already enrolled") from exc
        except Exception:
            self.db.rollback()
            raise

    def remove_student(self, course_id: UUID, student_id: UUID) -> None:
        self.get(course_id)
        try:
            if not self.courses.remove_student(course_id=course_id, student_id=student_id):
                raise CourseNotFound("Student enrollment not found")
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
