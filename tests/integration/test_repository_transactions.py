
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from ai_grading_iot.db.session import get_engine

from ai_grading_iot.repositories.user_repository import UserRepository
from ai_grading_iot.repositories.course_repository import CourseRepository
from ai_grading_iot.repositories.practice_repository import PracticeRepository
from ai_grading_iot.repositories.rubric_repository import RubricRepository
from ai_grading_iot.repositories.submission_repository import SubmissionRepository
from ai_grading_iot.repositories.grading_repository import GradingRepository

from ai_grading_iot.schemas.practice import (
    Practice,
    PracticeEnvironment,
    PracticeMetadata,
    PracticeRequirements,
    PracticeRubricReference,
    PracticeTask,
)
from ai_grading_iot.schemas.rubric import Rubric, RubricType
from ai_grading_iot.schemas.submission import Submission, SubmissionStatus


@pytest.fixture
def session_factory():
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        expire_on_commit=False,
    )


def create_full_workflow(db: Session):
    user_repo = UserRepository(db)
    course_repo = CourseRepository(db)
    practice_repo = PracticeRepository(db)
    rubric_repo = RubricRepository(db)
    submission_repo = SubmissionRepository(db)

    run_id = uuid4().hex

    # 1. Create Teacher and Student
    teacher = user_repo.create(
        email=f"teacher_{run_id}@example.com",
        password_hash="test_hash",
        full_name="Integration Teacher",
        role="teacher",
    )

    student = user_repo.create(
        email=f"student_{run_id}@example.com",
        password_hash="test_hash",
        full_name="Integration Student",
        role="student",
    )

    # 2. Create Course
    course = course_repo.create(
        code=f"TX_{run_id[:12]}",
        name="Integration IoT Course",
        description="Repository transaction testing",
    )

    # 3. Assign Teacher and enroll Student
    course_repo.assign_teacher(
        course_id=course.id,
        teacher_id=teacher.id,
    )

    course_repo.enroll_student(
        course_id=course.id,
        student_id=student.id,
    )

    # 4. Create Practice
    practice_schema = Practice(
        title="ESP32 Sensor Practice",
        description="Read and process sensor data",
        requirements=PracticeRequirements(
            objective="Read sensor data using ESP32",
            tasks=[
                PracticeTask(
                    order=1,
                    description="Initialize sensor",
                ),
                PracticeTask(
                    order=2,
                    description="Read sensor values",
                ),
            ],
            constraints=["Use ESP32"],
        ),
        environment=PracticeEnvironment(
            board="ESP32",
            framework="Arduino",
            language="C++",
            libraries=[],
        ),
        rubric=PracticeRubricReference(),
        metadata=PracticeMetadata(
            created_by="integration_teacher",
        ),
    )

    practice = practice_repo.create(
        course_id=course.id,
        practice=practice_schema,
    )

    # 5. Create Code, Data and Vision Rubrics
    rubric_specs = [
        (RubricType.CODE, 50.0, ["Correct code", "GPIO setup"]),
        (RubricType.DATA, 30.0, ["Valid sensor values"]),
        (RubricType.VISION, 20.0, ["Correct kit wiring"]),
    ]

    rubrics = {}

    for rubric_type, weight, criteria in rubric_specs:
        rubric = rubric_repo.create(
            practice_id=practice.id,
            rubric=Rubric(
                type=rubric_type,
                weight=weight,
                criteria=criteria,
            ),
        )
        rubrics[rubric_type.value] = rubric

    # 6. Link Rubric IDs into Practice JSONB
    practice.rubric_reference = {
        "code_rubric_id": str(rubrics["code"].id),
        "dashboard_rubric_id": str(rubrics["data"].id),
        "vision_rubric_id": str(rubrics["vision"].id),
    }
    db.flush()

    # 7. Create Submission
    submission = submission_repo.create(
        submission=Submission(
            practice_id=practice.id,
            student_id=student.id,
            description="ESP32 implementation",
            code="void setup() {}",
            images=["integration/kit_01.jpg"],
            status=SubmissionStatus.SUBMITTED,
            submitted_at=datetime.now(timezone.utc),
        )
    )

    return {
        "teacher_id": teacher.id,
        "student_id": student.id,
        "course_id": course.id,
        "course_code": course.code,
        "practice_id": practice.id,
        "rubric_ids": {
            key: value.id for key, value in rubrics.items()
        },
        "submission_id": submission.id,
    }


def test_full_workflow_commit(session_factory):
    # Transaction 1: Create all records and commit
    with session_factory.begin() as db:
        data = create_full_workflow(db)

        grading_repo = GradingRepository(db)

        result = grading_repo.create(
            submission_id=data["submission_id"],
            code_score=90,
            data_score=85,
        )

        grading_id = result.id

    # Transaction 2: Verify using a new session
    with session_factory() as db:
        user_repo = UserRepository(db)
        course_repo = CourseRepository(db)
        practice_repo = PracticeRepository(db)
        rubric_repo = RubricRepository(db)
        submission_repo = SubmissionRepository(db)
        grading_repo = GradingRepository(db)

        teacher = user_repo.get_by_id(data["teacher_id"])
        student = user_repo.get_by_id(data["student_id"])
        course = course_repo.get_by_id(data["course_id"])
        practice = practice_repo.get_by_id(data["practice_id"])
        submission = submission_repo.get_by_id(
            data["submission_id"]
        )
        grading = grading_repo.get_by_id(grading_id)

        assert teacher is not None
        assert student is not None
        assert course is not None
        assert practice is not None
        assert submission is not None
        assert grading is not None

        assert grading.submission_id == submission.id
        assert grading.code_score == 90
        assert grading.data_score == 85
        assert grading.vision_score is None

        assert len(
            course_repo.get_teachers(course.id)
        ) == 1

        assert len(
            course_repo.get_students(course.id)
        ) == 1

        rubrics = rubric_repo.get_by_practice(practice.id)

        assert len(rubrics) == 3
        assert {r.type for r in rubrics} == {
            "code", "data", "vision"
        }

        assert practice.rubric_reference == {
            "code_rubric_id": str(data["rubric_ids"]["code"]),
            "dashboard_rubric_id": str(data["rubric_ids"]["data"]),
            "vision_rubric_id": str(data["rubric_ids"]["vision"]),
        }

def test_full_workflow_rollback(session_factory):
    course_code = None

    with pytest.raises(RuntimeError):
        with session_factory.begin() as db:
            data = create_full_workflow(db)
            course_code = data["course_code"]

            # Simulate a failure before commit
            raise RuntimeError("Simulated transaction failure")

    assert course_code is not None

    # Open another session to verify rollback
    with session_factory() as db:
        course_repo = CourseRepository(db)

        course = course_repo.get_by_code(course_code)

        assert course is None

def test_foreign_key_constraint(session_factory):
    nonexistent_submission_id = uuid4()

    with pytest.raises(IntegrityError):
        with session_factory.begin() as db:
            grading_repo = GradingRepository(db)

            grading_repo.create(
                submission_id=nonexistent_submission_id,
                code_score=85,
            )

def test_unique_constraint(session_factory):
    with pytest.raises(IntegrityError):
        with session_factory.begin() as db:
            data = create_full_workflow(db)
            grading_repo = GradingRepository(db)

            grading_repo.create(
                submission_id=data["submission_id"],
                code_score=80,
            )

            # Must fail: same submission_id
            grading_repo.create(
                submission_id=data["submission_id"],
                code_score=95,
            )

def test_resubmission_invalidates_grading(session_factory):
    # Step 1: Create and grade an initial submission
    with session_factory.begin() as db:
        data = create_full_workflow(db)

        grading_repo = GradingRepository(db)

        old_result = grading_repo.create(
            submission_id=data["submission_id"],
            code_score=70,
        )
        old_grading_id = old_result.id

    # Step 2: Resubmit and invalidate the old grade
    with session_factory.begin() as db:
        submission_repo = SubmissionRepository(db)
        grading_repo = GradingRepository(db)

        submission = submission_repo.get_by_id(
            data["submission_id"]
        )
        assert submission is not None

        existing_result = grading_repo.get_by_submission(
            submission.id
        )
        assert existing_result is not None

        grading_repo.delete(existing_result)

        updated_schema = submission_repo.to_schema(submission)
        updated_schema.code = (
            "void setup() { pinMode(2, OUTPUT); }"
        )
        updated_schema.submitted_at = datetime.now(
            timezone.utc
        )
        updated_schema.status = SubmissionStatus.SUBMITTED

        submission_repo.update(
            submission,
            submission=updated_schema,
        )

    # Step 3: Verify after committing
    with session_factory() as db:
        submission_repo = SubmissionRepository(db)
        grading_repo = GradingRepository(db)

        submission = submission_repo.get_by_id(
            data["submission_id"]
        )
        assert submission is not None

        assert submission.id == data["submission_id"]
        assert "pinMode" in submission.code

        assert grading_repo.get_by_id(
            old_grading_id
        ) is None

        assert grading_repo.get_by_submission(
            submission.id
        ) is None

    # Step 4: Store a new grading result
    with session_factory.begin() as db:
        grading_repo = GradingRepository(db)

        new_result = grading_repo.create(
            submission_id=data["submission_id"],
            code_score=95,
        )
        new_grading_id = new_result.id

    with session_factory() as db:
        grading_repo = GradingRepository(db)

        result = grading_repo.get_by_submission(
            data["submission_id"]
        )

        assert result is not None
        assert result.id == new_grading_id
        assert result.id != old_grading_id
        assert result.code_score == 95

def test_jsonb_persistence(session_factory):
    # Create and commit data
    with session_factory.begin() as db:
        data = create_full_workflow(db)

        grading_repo = GradingRepository(db)

        grading_repo.create(
            submission_id=data["submission_id"],
            code_score=85,
        )

    # Read using a new session
    with session_factory() as db:
        practice_repo = PracticeRepository(db)
        rubric_repo = RubricRepository(db)
        submission_repo = SubmissionRepository(db)

        practice = practice_repo.get_by_id(
            data["practice_id"]
        )
        assert practice is not None

        assert practice.requirements["objective"] == (
            "Read sensor data using ESP32"
        )
        assert len(practice.requirements["tasks"]) == 2

        assert practice.environment["board"] == "ESP32"

        assert practice.rubric_reference[
            "code_rubric_id"
        ] == str(data["rubric_ids"]["code"])

        # ORM -> Pydantic conversion
        restored_practice = practice_repo.to_schema(
            practice
        )

        assert restored_practice.practice_id == practice.id
        assert len(restored_practice.requirements.tasks) == 2

        # Rubric JSONB
        code_rubric = rubric_repo.get_by_type(
            practice.id,
            RubricType.CODE,
        )

        assert code_rubric is not None
        assert code_rubric.criteria == [
            "Correct code",
            "GPIO setup",
        ]

        # Submission images JSONB
        submission = submission_repo.get_by_id(
            data["submission_id"]
        )

        assert submission is not None
        assert submission.images == [
            "integration/kit_01.jpg"
        ]
