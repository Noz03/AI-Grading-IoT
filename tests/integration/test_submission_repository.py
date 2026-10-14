
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_grading_iot.db.session import get_engine
from ai_grading_iot.repositories.course_repository import CourseRepository
from ai_grading_iot.repositories.practice_repository import PracticeRepository
from ai_grading_iot.repositories.user_repository import UserRepository
from ai_grading_iot.repositories.submission_repository import SubmissionRepository

from ai_grading_iot.schemas.practice import (
    Practice,
    PracticeEnvironment,
    PracticeMetadata,
    PracticeRequirements,
    PracticeRubricReference,
    PracticeTask,
)
from ai_grading_iot.schemas.submission import (
    Submission,
    SubmissionStatus,
)


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
    return SubmissionRepository(db_session)


@pytest.fixture
def practice(db_session):
    course_repo = CourseRepository(db_session)
    practice_repo = PracticeRepository(db_session)

    course = course_repo.create(
        code=f"IOT_{uuid4().hex[:10]}",
        name="IoT Fundamentals",
    )

    schema = Practice(
        title="ESP32 LED Control",
        description="Điều khiển LED bằng ESP32",
        requirements=PracticeRequirements(
            objective="Điều khiển LED",
            tasks=[
                PracticeTask(
                    order=1,
                    description="Khởi tạo GPIO",
                )
            ],
        ),
        environment=PracticeEnvironment(
            board="ESP32",
            framework="Arduino",
            language="C++",
        ),
        rubric=PracticeRubricReference(),
        metadata=PracticeMetadata(
            created_by="test_teacher",
        ),
    )

    return practice_repo.create(
        course_id=course.id,
        practice=schema,
    )


@pytest.fixture
def student(db_session):
    user_repo = UserRepository(db_session)

    return user_repo.create(
        email=f"student_{uuid4().hex}@example.com",
        password_hash="fake_hash_for_testing",
        full_name="Test Student",
        role="student",
    )


def make_submission_schema(
    practice,
    student,
    *,
    status=SubmissionStatus.DRAFT,
):
    return Submission(
        practice_id=practice.id,
        student_id=student.id,
        description="Bài thực hành ESP32",
        code="void setup() {}",
        images=[
            "submissions/kit_01.jpg",
            "submissions/kit_02.jpg",
        ],
        status=status,
        submitted_at=(
            datetime.now(timezone.utc)
            if status == SubmissionStatus.SUBMITTED
            else None
        ),
    )


def make_submission(repository, practice, student):
    schema = make_submission_schema(practice, student)

    return repository.create(submission=schema)


# =====================================
# CREATE
# =====================================

def test_create_submission(repository, practice, student):
    model = make_submission(repository, practice, student)

    assert model.id is not None
    assert model.practice_id == practice.id
    assert model.student_id == student.id
    assert model.status == "draft"


def test_submission_images_jsonb(repository, practice, student):
    model = make_submission(repository, practice, student)

    assert model.images == [
        "submissions/kit_01.jpg",
        "submissions/kit_02.jpg",
    ]


# =====================================
# READ
# =====================================

def test_get_by_id(repository, practice, student):
    model = make_submission(repository, practice, student)

    found = repository.get_by_id(model.id)

    assert found is not None
    assert found.id == model.id


def test_get_nonexistent_submission(repository):
    assert repository.get_by_id(uuid4()) is None


def test_get_by_practice_and_student(repository, practice, student):
    model = make_submission(repository, practice, student)

    found = repository.get_by_practice_and_student(
        practice_id=practice.id,
        student_id=student.id,
    )

    assert found is not None
    assert found.id == model.id


def test_get_by_practice(repository, practice, student):
    model = make_submission(repository, practice, student)

    result = repository.get_by_practice(practice.id)

    assert model.id in {item.id for item in result}


def test_get_by_student(repository, practice, student):
    model = make_submission(repository, practice, student)

    result = repository.get_by_student(student.id)

    assert model.id in {item.id for item in result}


# =====================================
# UPDATE / RESUBMISSION
# =====================================

def test_update_submission(repository, practice, student):
    model = make_submission(repository, practice, student)

    original_id = model.id

    schema = repository.to_schema(model)

    schema.code = "void setup() { pinMode(2, OUTPUT); }"
    schema.description = "Bài làm đã cập nhật"
    schema.status = SubmissionStatus.SUBMITTED
    schema.submitted_at = datetime.now(timezone.utc)

    updated = repository.update(
        model,
        submission=schema,
    )

    assert updated.id == original_id
    assert updated.status == "submitted"
    assert updated.code == schema.code
    assert updated.submitted_at is not None


def test_update_invalid_id(repository, practice, student):
    model = make_submission(repository, practice, student)

    schema = repository.to_schema(model)
    schema.id = uuid4()

    with pytest.raises(ValueError):
        repository.update(model, submission=schema)


def test_cannot_change_practice(repository, practice, student):
    model = make_submission(repository, practice, student)

    schema = repository.to_schema(model)
    schema.practice_id = uuid4()

    with pytest.raises(ValueError):
        repository.update(model, submission=schema)


def test_cannot_change_student(repository, practice, student):
    model = make_submission(repository, practice, student)

    schema = repository.to_schema(model)
    schema.student_id = uuid4()

    with pytest.raises(ValueError):
        repository.update(model, submission=schema)


# =====================================
# DELETE
# =====================================

def test_delete_submission(repository, practice, student):
    model = make_submission(repository, practice, student)

    submission_id = model.id

    repository.delete(model)

    assert repository.get_by_id(submission_id) is None


# =====================================
# SCHEMA CONVERSION
# =====================================

def test_orm_to_pydantic(repository, practice, student):
    model = make_submission(repository, practice, student)

    schema = repository.to_schema(model)

    assert isinstance(schema, Submission)
    assert schema.id == model.id
    assert schema.practice_id == practice.id
    assert schema.student_id == student.id
    assert len(schema.images) == 2


def test_jsonb_round_trip(db_session, practice, student):
    repository = SubmissionRepository(db_session)

    model = make_submission(repository, practice, student)
    submission_id = model.id

    db_session.expunge_all()

    loaded = repository.get_by_id(submission_id)

    assert loaded is not None
    assert loaded.images == [
        "submissions/kit_01.jpg",
        "submissions/kit_02.jpg",
    ]


# =====================================
# DATABASE CONSTRAINTS
# =====================================

def test_duplicate_submission_rejected(
    repository,
    practice,
    student,
    db_session,
):
    make_submission(repository, practice, student)

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            make_submission(repository, practice, student)


# =====================================
# PAGINATION
# =====================================

def test_pagination_validation(repository, practice):
    with pytest.raises(ValueError):
        repository.get_by_practice(practice.id, limit=0)

    with pytest.raises(ValueError):
        repository.get_by_student(uuid4(), offset=-1)
