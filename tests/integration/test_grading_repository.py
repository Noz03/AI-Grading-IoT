
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_grading_iot.db.session import get_engine

from ai_grading_iot.repositories.user_repository import (
    UserRepository,
)
from ai_grading_iot.repositories.course_repository import (
    CourseRepository,
)
from ai_grading_iot.repositories.practice_repository import (
    PracticeRepository,
)
from ai_grading_iot.repositories.submission_repository import (
    SubmissionRepository,
)
from ai_grading_iot.repositories.grading_repository import (
    GradingRepository,
)

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

from ai_grading_iot.schemas.code_evaluation import (
    CodeEvaluation,
    CriterionResult,
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
    return GradingRepository(db_session)


@pytest.fixture
def submission(db_session):
    user_repo = UserRepository(db_session)
    course_repo = CourseRepository(db_session)
    practice_repo = PracticeRepository(db_session)
    submission_repo = SubmissionRepository(db_session)

    student = user_repo.create(
        email=f"student_{uuid4().hex}@example.com",
        password_hash="test_hash",
        full_name="Test Student",
        role="student",
    )

    course = course_repo.create(
        code=f"IOT_{uuid4().hex[:10]}",
        name="IoT Fundamentals",
    )

    practice_schema = Practice(
        title="ESP32 LED",
        description="Điều khiển LED",
        requirements=PracticeRequirements(
            objective="Điều khiển LED qua GPIO",
            tasks=[
                PracticeTask(
                    order=1,
                    description="Khởi tạo GPIO",
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

    practice = practice_repo.create(
        course_id=course.id,
        practice=practice_schema,
    )

    submission_schema = Submission(
        practice_id=practice.id,
        student_id=student.id,
        description="Bài làm ESP32",
        code="void setup() {}",
        status=SubmissionStatus.SUBMITTED,
        submitted_at=datetime.now(timezone.utc),
    )

    return submission_repo.create(
        submission=submission_schema,
    )


def make_evaluation():
    return CodeEvaluation(
        criteria_results=[
            CriterionResult(
                criterion="Khởi tạo GPIO",
                score=90,
                feedback="Khởi tạo đúng",
            ),
            CriterionResult(
                criterion="Điều khiển LED",
                score=80,
                feedback="Đáp ứng yêu cầu",
            ),
        ],
        code_score=85,
        overall_feedback="Bài làm khá tốt",
    )


def make_result(repository, submission):
    return repository.create(
        submission_id=submission.id,
        code_score=85,
        code_evaluation=make_evaluation(),
    )


# =====================================
# CREATE
# =====================================

def test_create_grading_result(repository, submission):
    result = make_result(repository, submission)

    assert result.id is not None
    assert result.submission_id == submission.id
    assert result.code_score == 85
    assert result.data_score is None
    assert result.vision_score is None
    assert result.final_score is None


def test_create_partial_result(repository, submission):
    result = repository.create(
        submission_id=submission.id,
        code_score=90,
    )

    assert result.code_score == 90
    assert result.data_score is None
    assert result.vision_score is None
    assert result.final_score is None


def test_create_result_with_all_scores(repository, submission):
    result = repository.create(
        submission_id=submission.id,
        code_score=90,
        data_score=80,
        vision_score=70,
        final_score=82,
    )

    assert result.code_score == 90
    assert result.data_score == 80
    assert result.vision_score == 70
    assert result.final_score == 82


# =====================================
# READ
# =====================================

def test_get_by_id(repository, submission):
    result = make_result(repository, submission)

    found = repository.get_by_id(result.id)

    assert found is not None
    assert found.id == result.id


def test_get_by_submission(repository, submission):
    result = make_result(repository, submission)

    found = repository.get_by_submission(submission.id)

    assert found is not None
    assert found.id == result.id


def test_get_nonexistent_result(repository):
    assert repository.get_by_id(uuid4()) is None


def test_get_nonexistent_submission_result(repository):
    assert repository.get_by_submission(uuid4()) is None


# =====================================
# UPDATE
# =====================================

def test_update_grading_result(repository, submission):
    result = make_result(repository, submission)

    updated = repository.update(
        result,
        code_score=95,
        data_score=88,
    )

    assert updated.code_score == 95
    assert updated.data_score == 88
    assert updated.submission_id == submission.id


def test_update_preserves_other_scores(repository, submission):
    result = make_result(repository, submission)

    repository.update(
        result,
        data_score=75,
    )

    assert result.code_score == 85
    assert result.data_score == 75


# =====================================
# SAVE OR UPDATE
# =====================================

def test_save_or_update_creates(repository, submission):
    result = repository.save_or_update(
        submission_id=submission.id,
        code_score=85,
    )

    assert result.id is not None
    assert result.code_score == 85


def test_save_or_update_updates(repository, submission):
    first = repository.save_or_update(
        submission_id=submission.id,
        code_score=80,
    )

    second = repository.save_or_update(
        submission_id=submission.id,
        code_score=95,
    )

    assert second.id == first.id
    assert second.code_score == 95


# =====================================
# DELETE
# =====================================

def test_delete_result(repository, submission):
    result = make_result(repository, submission)
    grading_id = result.id

    repository.delete(result)

    assert repository.get_by_id(grading_id) is None


# =====================================
# JSONB
# =====================================

def test_code_evaluation_jsonb(repository, submission):
    result = make_result(repository, submission)

    assert result.code_evaluation is not None
    assert len(
        result.code_evaluation["criteria_results"]
    ) == 2


def test_code_evaluation_round_trip(
    repository,
    submission,
    db_session,
):
    result = make_result(repository, submission)
    grading_id = result.id

    db_session.expunge_all()

    loaded = repository.get_by_id(grading_id)

    assert loaded is not None

    evaluation = repository.get_code_evaluation(loaded)

    assert evaluation is not None
    assert evaluation.code_score == 85
    assert evaluation.overall_feedback == "Bài làm khá tốt"


# =====================================
# SCHEMA CONVERSION
# =====================================

def test_to_schema_complete(repository, submission):
    model = repository.create(
        submission_id=submission.id,
        code_score=85,
        vision_score=70,
        final_score=80,
    )

    schema = repository.to_schema(model)

    assert schema.code_score == 85
    assert schema.vision_score == 70
    assert schema.final_score == 80


def test_to_schema_partial_is_supported(repository, submission):
    model = make_result(repository, submission)
    schema = repository.to_schema(model)
    assert schema.code_score == model.code_score
    assert schema.vision_score is None
    assert schema.final_score is None
    assert schema.status == "partial"


# =====================================
# CONSTRAINTS
# =====================================

def test_duplicate_result_rejected(
    repository,
    submission,
    db_session,
):
    make_result(repository, submission)

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            make_result(repository, submission)


def test_invalid_score_rejected(
    repository,
    submission,
    db_session,
):
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            repository.create(
                submission_id=submission.id,
                code_score=150,
            )
