
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from ai_grading_iot.db.session import get_engine
from ai_grading_iot.repositories.course_repository import CourseRepository
from ai_grading_iot.repositories.practice_repository import PracticeRepository
from ai_grading_iot.schemas.practice import (
    Practice,
    PracticeEnvironment,
    PracticeHardware,
    PracticeMetadata,
    PracticeRequirements,
    PracticeRubricReference,
    PracticeStatus,
    PracticeTask,
)

from sqlalchemy import select
from ai_grading_iot.models.practice import Practice as PracticeModel


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
    return PracticeRepository(db_session)


@pytest.fixture
def course_repository(db_session):
    return CourseRepository(db_session)


@pytest.fixture
def course(course_repository):
    return course_repository.create(
        code=f"IOT_{uuid4().hex[:10]}",
        name="IoT Fundamentals",
        description="Khóa học IoT",
    )


def make_practice_schema(
    *,
    status=PracticeStatus.DRAFT,
):
    return Practice(
        title="ESP32 LED Control",
        description="Điều khiển LED bằng ESP32",
        requirements=PracticeRequirements(
            objective="Điều khiển LED bật và tắt",
            tasks=[
                PracticeTask(
                    order=1,
                    description="Khởi tạo GPIO",
                ),
                PracticeTask(
                    order=2,
                    description="Điều khiển LED",
                ),
            ],
            constraints=["Sử dụng ESP32"],
        ),
        environment=PracticeEnvironment(
            board="ESP32",
            framework="Arduino",
            language="C++",
            libraries=[],
        ),
        hardware=[
            PracticeHardware(
                name="ESP32",
                type="microcontroller",
            ),
            PracticeHardware(
                name="LED",
                type="actuator",
            ),
        ],
        rubric=PracticeRubricReference(),
        version="1.0",
        status=status,
        metadata=PracticeMetadata(
            created_by="test_teacher",
        ),
    )


def make_practice(
    repository,
    course,
    *,
    status=PracticeStatus.DRAFT,
):
    schema = make_practice_schema(status=status)

    return repository.create(
        course_id=course.id,
        practice=schema,
    )


# ==================================
# CREATE
# ==================================

def test_create_practice(repository, course):
    practice = make_practice(repository, course)

    assert practice.id is not None
    assert practice.course_id == course.id
    assert practice.title == "ESP32 LED Control"
    assert practice.status == "draft"


def test_create_practice_jsonb(repository, course):
    practice = make_practice(repository, course)

    assert practice.requirements["objective"] == (
        "Điều khiển LED bật và tắt"
    )

    assert len(practice.requirements["tasks"]) == 2
    assert practice.environment["board"] == "ESP32"
    assert len(practice.hardware) == 2

    # UUID bên trong JSONB phải được serialize thành string
    assert isinstance(
        practice.requirements["tasks"][0]["id"],
        str,
    )


# ==================================
# READ
# ==================================

def test_get_practice_by_id(repository, course):
    practice = make_practice(repository, course)

    found = repository.get_by_id(practice.id)

    assert found is not None
    assert found.id == practice.id


def test_get_nonexistent_practice(repository):
    assert repository.get_by_id(uuid4()) is None


def test_get_practices_by_course(repository, course):
    first = make_practice(repository, course)
    second = make_practice(repository, course)

    practices = repository.get_by_course(
        course.id,
        limit=100,
    )

    practice_ids = {
        item.id for item in practices
    }

    assert first.id in practice_ids
    assert second.id in practice_ids


def test_get_practices_by_status(repository, course):
    draft = make_practice(
        repository,
        course,
        status=PracticeStatus.DRAFT,
    )

    published = make_practice(
        repository,
        course,
        status=PracticeStatus.PUBLISHED,
    )

    result = repository.get_by_status(
        course.id,
        PracticeStatus.PUBLISHED,
    )

    result_ids = {item.id for item in result}

    assert published.id in result_ids
    assert draft.id not in result_ids


# ==================================
# UPDATE
# ==================================

def test_update_practice(repository, course):
    model = make_practice(repository, course)

    schema = repository.to_schema(model)
    schema.title = "Advanced ESP32"
    schema.status = PracticeStatus.PUBLISHED

    updated = repository.update(
        model,
        practice=schema,
    )

    assert updated.title == "Advanced ESP32"
    assert updated.status == "published"


def test_update_practice_invalid_id(repository, course):
    model = make_practice(repository, course)

    schema = repository.to_schema(model)
    schema.practice_id = uuid4()

    with pytest.raises(ValueError):
        repository.update(
            model,
            practice=schema,
        )


# ==================================
# DELETE
# ==================================

def test_delete_practice(repository, course):
    model = make_practice(repository, course)
    practice_id = model.id

    repository.delete(model)

    assert repository.get_by_id(practice_id) is None


# ==================================
# SCHEMA CONVERSION
# ==================================

def test_orm_to_pydantic_schema(repository, course):
    model = make_practice(repository, course)

    schema = repository.to_schema(model)

    assert isinstance(schema, Practice)
    assert schema.practice_id == model.id

    assert schema.environment.board == "ESP32"
    assert len(schema.requirements.tasks) == 2
    assert len(schema.hardware) == 2

    assert schema.requirements.tasks[0].order == 1


# ==================================
# VALIDATION
# ==================================

def test_pagination_validation(repository, course):
    with pytest.raises(ValueError):
        repository.get_by_course(
            course.id,
            limit=0,
        )

    with pytest.raises(ValueError):
        repository.get_by_course(
            course.id,
            offset=-1,
        )


def test_jsonb_round_trip(db_session, course):
    repository = PracticeRepository(db_session)

    original = make_practice_schema()

    model = repository.create(
        course_id=course.id,
        practice=original,
    )

    practice_id = model.id

    db_session.expunge_all()

    statement = select(PracticeModel).where(
        PracticeModel.id == practice_id
    )

    loaded = db_session.scalar(statement)

    assert loaded is not None

    restored = repository.to_schema(loaded)

    assert restored.practice_id == original.practice_id
    assert restored.requirements == original.requirements
    assert restored.environment == original.environment
    assert restored.hardware == original.hardware
    assert restored.rubric == original.rubric
    assert restored.metadata == original.metadata