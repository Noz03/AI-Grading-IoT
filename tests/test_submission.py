from datetime import datetime, timezone
from uuid import UUID
import pytest
from pydantic import ValidationError

from ai_grading_iot.schemas.submission import Submission, SubmissionStatus


def test_create_default_submission():
    practice_uuid = UUID("550e8400-e29b-41d4-a716-446655440000")
    student_uuid = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

    submission = Submission(
        practice_id=practice_uuid,
        student_id=student_uuid,
        description="Test submission",
        code="void setup() {}",
        images=["kit.jpg"],
    )

    assert isinstance(submission.id, UUID)
    assert submission.practice_id == practice_uuid
    assert submission.student_id == student_uuid
    assert submission.description == "Test submission"
    assert submission.code == "void setup() {}"
    assert submission.images == ["kit.jpg"]
    assert submission.status == SubmissionStatus.DRAFT
    assert submission.submitted_at is None


def test_submitted_submission():
    now = datetime.now(timezone.utc)
    submission = Submission(
        practice_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        student_id=UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8"),
        description="Submitted report",
        code="void setup() { pinMode(2, OUTPUT); }",
        images=["front.jpg", "wiring.jpg"],
        status=SubmissionStatus.SUBMITTED,
        submitted_at=now,
    )

    assert submission.status == SubmissionStatus.SUBMITTED
    assert submission.submitted_at == now


def test_submission_id_is_generated_automatically():
    sub1 = Submission(
        practice_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        student_id=UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8"),
        description="Test 1",
        code="print(1)",
        images=[],
    )
    sub2 = Submission(
        practice_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        student_id=UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8"),
        description="Test 2",
        code="print(2)",
        images=[],
    )

    assert isinstance(sub1.id, UUID)
    assert isinstance(sub2.id, UUID)
    assert sub1.id != sub2.id


def test_uuid_from_string_parsing():
    submission = Submission(
        practice_id="550e8400-e29b-41d4-a716-446655440000",  # type: ignore
        student_id="6ba7b810-9dad-11d1-80b4-00c04fd430c8",  # type: ignore
        description="Valid UUID string coercion",
        code="code",
        images=[],
    )

    assert isinstance(submission.practice_id, UUID)
    assert isinstance(submission.student_id, UUID)


def test_invalid_practice_id():
    with pytest.raises(ValidationError):
        Submission(
            practice_id="invalid-uuid-format",  # type: ignore
            student_id=UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8"),
            description="Test",
            code="code",
            images=[],
        )


def test_invalid_student_id():
    with pytest.raises(ValidationError):
        Submission(
            practice_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            student_id="student-001",  # type: ignore
            description="Test",
            code="code",
            images=[],
        )


def test_invalid_status():
    with pytest.raises(ValidationError):
        Submission(
            practice_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            student_id=UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8"),
            description="Test",
            code="code",
            images=[],
            status="completed",  # type: ignore
        )


def test_invalid_images_type():
    with pytest.raises(ValidationError):
        Submission(
            practice_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            student_id=UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8"),
            description="Test",
            code="code",
            images="kit.jpg",  # type: ignore
        )
