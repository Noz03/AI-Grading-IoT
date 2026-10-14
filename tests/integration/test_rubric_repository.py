
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_grading_iot.db.session import get_engine
from ai_grading_iot.repositories.course_repository import CourseRepository
from ai_grading_iot.repositories.practice_repository import PracticeRepository
from ai_grading_iot.repositories.rubric_repository import RubricRepository

from ai_grading_iot.schemas.practice import (
    Practice,
    PracticeEnvironment,
    PracticeMetadata,
    PracticeRequirements,
    PracticeRubricReference,
    PracticeTask,
)
from ai_grading_iot.schemas.rubric import (
    Rubric,
    RubricType,
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
    return RubricRepository(db_session)


@pytest.fixture
def practice(db_session):
    course_repo = CourseRepository(db_session)
    practice_repo = PracticeRepository(db_session)

    course = course_repo.create(
        code=f"IOT_{uuid4().hex[:10]}",
        name="IoT Fundamentals",
    )

    practice_schema = Practice(
        title="ESP32 Sensor",
        description="Đọc dữ liệu cảm biến bằng ESP32",
        requirements=PracticeRequirements(
            objective="Đọc và xử lý dữ liệu cảm biến",
            tasks=[
                PracticeTask(
                    order=1,
                    description="Đọc cảm biến",
                ),
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
        practice=practice_schema,
    )


def make_rubric(
    repository,
    practice,
    rubric_type=RubricType.CODE,
):
    schema = Rubric(
        type=rubric_type,
        weight=30,
        criteria=[
            "Đáp ứng yêu cầu bài thực hành",
            "Đảm bảo tính chính xác",
        ],
    )

    return repository.create(
        practice_id=practice.id,
        rubric=schema,
    )


def test_create_code_rubric(repository, practice):
    rubric = make_rubric(repository, practice)

    assert rubric.id is not None
    assert rubric.practice_id == practice.id
    assert rubric.type == "code"


def test_create_all_three_types(repository, practice):
    for rubric_type in RubricType:
        make_rubric(repository, practice, rubric_type)

    rubrics = repository.get_by_practice(practice.id)

    assert len(rubrics) == 3
    assert {r.type for r in rubrics} == {
        "code", "data", "vision"
    }


def test_get_by_id(repository, practice):
    rubric = make_rubric(repository, practice)

    found = repository.get_by_id(rubric.id)

    assert found is not None
    assert found.id == rubric.id


def test_get_nonexistent_rubric(repository):
    assert repository.get_by_id(uuid4()) is None


def test_get_by_practice(repository, practice):
    make_rubric(repository, practice, RubricType.CODE)
    make_rubric(repository, practice, RubricType.DATA)

    result = repository.get_by_practice(practice.id)

    assert len(result) == 2


def test_get_by_type(repository, practice):
    make_rubric(repository, practice, RubricType.CODE)
    make_rubric(repository, practice, RubricType.DATA)

    found = repository.get_by_type(
        practice.id,
        RubricType.DATA,
    )

    assert found is not None
    assert found.type == "data"


def test_get_by_type_not_found(repository, practice):
    assert repository.get_by_type(
        practice.id,
        RubricType.VISION,
    ) is None


def test_update_rubric(repository, practice):
    model = make_rubric(repository, practice)

    schema = repository.to_schema(model)
    schema.weight = 40
    schema.criteria = [
        "Tiêu chí mới 1",
        "Tiêu chí mới 2",
    ]

    updated = repository.update(
        model,
        rubric=schema,
    )

    assert updated.weight == 40
    assert updated.criteria == schema.criteria


def test_update_invalid_id(repository, practice):
    model = make_rubric(repository, practice)

    schema = repository.to_schema(model)
    schema.id = uuid4()

    with pytest.raises(ValueError):
        repository.update(model, rubric=schema)


def test_update_cannot_change_type(repository, practice):
    model = make_rubric(repository, practice)

    schema = repository.to_schema(model)
    schema.type = RubricType.DATA

    with pytest.raises(ValueError):
        repository.update(model, rubric=schema)


def test_delete_rubric(repository, practice):
    model = make_rubric(repository, practice)
    rubric_id = model.id

    repository.delete(model)

    assert repository.get_by_id(rubric_id) is None


def test_orm_to_schema(repository, practice):
    model = make_rubric(repository, practice)

    schema = repository.to_schema(model)

    assert isinstance(schema, Rubric)
    assert schema.id == model.id
    assert schema.type == RubricType.CODE
    assert len(schema.criteria) == 2


def test_jsonb_round_trip(db_session, practice):
    repository = RubricRepository(db_session)

    model = make_rubric(repository, practice)
    rubric_id = model.id
    original_criteria = list(model.criteria)

    db_session.expunge_all()

    loaded = repository.get_by_id(rubric_id)

    assert loaded is not None
    assert loaded.criteria == original_criteria

    restored = repository.to_schema(loaded)
    assert restored.criteria == original_criteria


def test_duplicate_type_rejected(
    repository,
    practice,
    db_session,
):
    make_rubric(repository, practice, RubricType.CODE)

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            make_rubric(
                repository,
                practice,
                RubricType.CODE,
            )
