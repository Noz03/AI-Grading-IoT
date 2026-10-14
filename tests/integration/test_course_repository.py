
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_grading_iot.db.session import get_engine
from ai_grading_iot.repositories.course_repository import CourseRepository
from ai_grading_iot.repositories.user_repository import UserRepository


@pytest.fixture
def db_session():
    engine = get_engine()

    with engine.connect() as connection:
        transaction = connection.begin()

        with Session(
            bind=connection,
            autoflush=False,
            expire_on_commit=False,
        ) as session:
            try:
                yield session
            finally:
                session.close()
                if transaction.is_active:
                    transaction.rollback()


@pytest.fixture
def repository(db_session):
    return CourseRepository(db_session)


@pytest.fixture
def user_repository(db_session):
    return UserRepository(db_session)


def make_course(repository):
    return repository.create(
        code=f"IOT_{uuid4().hex[:10]}",
        name="Internet of Things",
        description="IoT Practice Course",
    )


def make_user(user_repository, role="student"):
    return user_repository.create(
        email=f"user_{uuid4().hex}@example.com",
        password_hash="fake_hash_for_testing",
        full_name="Test User",
        role=role,
    )


# =====================================
# COURSE CRUD
# =====================================

def test_create_course(repository):
    course = make_course(repository)

    assert course.id is not None
    assert course.name == "Internet of Things"


def test_get_course_by_id(repository):
    course = make_course(repository)

    found = repository.get_by_id(course.id)

    assert found is not None
    assert found.id == course.id


def test_get_course_by_code(repository):
    course = make_course(repository)

    found = repository.get_by_code(course.code)

    assert found is not None
    assert found.code == course.code


def test_get_nonexistent_course(repository):
    assert repository.get_by_id(uuid4()) is None


def test_get_all_courses(repository):
    first = make_course(repository)
    second = make_course(repository)

    courses = repository.get_all(limit=100)
    course_ids = {course.id for course in courses}

    assert first.id in course_ids
    assert second.id in course_ids


def test_update_course(repository):
    course = make_course(repository)

    updated = repository.update(
        course,
        name="Advanced IoT",
        description="Updated Description",
    )

    assert updated.name == "Advanced IoT"
    assert updated.description == "Updated Description"


def test_delete_course(repository):
    course = make_course(repository)
    course_id = course.id

    repository.delete(course)

    assert repository.get_by_id(course_id) is None


def test_pagination_validation(repository):
    with pytest.raises(ValueError):
        repository.get_all(limit=0)

    with pytest.raises(ValueError):
        repository.get_all(limit=101)

    with pytest.raises(ValueError):
        repository.get_all(offset=-1)


# =====================================
# TEACHER MANAGEMENT
# =====================================

def test_assign_teacher(repository, user_repository):
    course = make_course(repository)
    teacher = make_user(user_repository, "teacher")

    assignment = repository.assign_teacher(
        course_id=course.id,
        teacher_id=teacher.id,
    )

    assert assignment.course_id == course.id
    assert assignment.teacher_id == teacher.id


def test_get_teachers(repository, user_repository):
    course = make_course(repository)
    teacher = make_user(user_repository, "teacher")

    repository.assign_teacher(
        course_id=course.id,
        teacher_id=teacher.id,
    )

    teachers = repository.get_teachers(course.id)

    assert teacher.id in {
        user.id for user in teachers
    }


def test_remove_teacher(repository, user_repository):
    course = make_course(repository)
    teacher = make_user(user_repository, "teacher")

    repository.assign_teacher(
        course_id=course.id,
        teacher_id=teacher.id,
    )

    removed = repository.remove_teacher(
        course_id=course.id,
        teacher_id=teacher.id,
    )

    assert removed is True
    assert repository.get_teachers(course.id) == []


def test_remove_nonexistent_teacher(repository):
    assert repository.remove_teacher(
        course_id=uuid4(),
        teacher_id=uuid4(),
    ) is False


# =====================================
# STUDENT MANAGEMENT
# =====================================

def test_enroll_student(repository, user_repository):
    course = make_course(repository)
    student = make_user(user_repository, "student")

    enrollment = repository.enroll_student(
        course_id=course.id,
        student_id=student.id,
    )

    assert enrollment.course_id == course.id
    assert enrollment.student_id == student.id


def test_get_students(repository, user_repository):
    course = make_course(repository)
    student = make_user(user_repository, "student")

    repository.enroll_student(
        course_id=course.id,
        student_id=student.id,
    )

    students = repository.get_students(course.id)

    assert student.id in {
        user.id for user in students
    }


def test_remove_student(repository, user_repository):
    course = make_course(repository)
    student = make_user(user_repository, "student")

    repository.enroll_student(
        course_id=course.id,
        student_id=student.id,
    )

    removed = repository.remove_student(
        course_id=course.id,
        student_id=student.id,
    )

    assert removed is True
    assert repository.get_students(course.id) == []


def test_remove_nonexistent_student(repository):
    assert repository.remove_student(
        course_id=uuid4(),
        student_id=uuid4(),
    ) is False


def test_duplicate_teacher_assignment(
    repository,
    user_repository,
    db_session,
):
    course = make_course(repository)
    teacher = make_user(user_repository, "teacher")

    repository.assign_teacher(
        course_id=course.id,
        teacher_id=teacher.id,
    )

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            repository.assign_teacher(
                course_id=course.id,
                teacher_id=teacher.id,
            )


def test_duplicate_student_enrollment(
    repository,
    user_repository,
    db_session,
):
    course = make_course(repository)
    student = make_user(user_repository, "student")

    repository.enroll_student(
        course_id=course.id,
        student_id=student.id,
    )

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            repository.enroll_student(
                course_id=course.id,
                student_id=student.id,
            )