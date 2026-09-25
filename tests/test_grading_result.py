from uuid import UUID
import pytest
from pydantic import ValidationError

from ai_grading_iot.schemas.grading_result import GradingResult


VALID_SUBMISSION_ID = UUID("550e8400-e29b-41d4-a716-446655440000")


def test_create_grading_result_with_all_scores():
    result = GradingResult(
        submission_id=VALID_SUBMISSION_ID,
        code_score=85.0,
        data_score=80.0,
        vision_score=90.0,
        final_score=85.0,
    )

    assert isinstance(result.id, UUID)
    assert result.submission_id == VALID_SUBMISSION_ID
    assert result.code_score == 85.0
    assert result.data_score == 80.0
    assert result.vision_score == 90.0
    assert result.final_score == 85.0


def test_data_score_defaults_to_none():
    result = GradingResult(
        submission_id=VALID_SUBMISSION_ID,
        code_score=80.0,
        vision_score=90.0,
        final_score=83.0,
    )

    assert result.data_score is None


def test_submission_id_string_parsing():
    result = GradingResult(
        submission_id="550e8400-e29b-41d4-a716-446655440000",  # type: ignore
        code_score=80.0,
        vision_score=90.0,
        final_score=85.0,
    )

    assert isinstance(result.submission_id, UUID)
    assert result.submission_id == VALID_SUBMISSION_ID


def test_grading_result_id_is_generated_automatically():
    result1 = GradingResult(
        submission_id=VALID_SUBMISSION_ID,
        code_score=80.0,
        vision_score=90.0,
        final_score=85.0,
    )
    result2 = GradingResult(
        submission_id=VALID_SUBMISSION_ID,
        code_score=90.0,
        vision_score=95.0,
        final_score=92.5,
    )

    assert isinstance(result1.id, UUID)
    assert isinstance(result2.id, UUID)
    assert result1.id != result2.id


def test_boundary_scores_valid():
    result_min = GradingResult(
        submission_id=VALID_SUBMISSION_ID,
        code_score=0.0,
        data_score=0.0,
        vision_score=0.0,
        final_score=0.0,
    )
    result_max = GradingResult(
        submission_id=VALID_SUBMISSION_ID,
        code_score=100.0,
        data_score=100.0,
        vision_score=100.0,
        final_score=100.0,
    )

    assert result_min.code_score == 0.0
    assert result_max.final_score == 100.0


def test_invalid_submission_id():
    with pytest.raises(ValidationError):
        GradingResult(
            submission_id="invalid-uuid-string",  # type: ignore
            code_score=80.0,
            vision_score=90.0,
            final_score=85.0,
        )


def test_invalid_code_score_below_zero():
    with pytest.raises(ValidationError):
        GradingResult(
            submission_id=VALID_SUBMISSION_ID,
            code_score=-1.0,
            vision_score=90.0,
            final_score=80.0,
        )


def test_invalid_code_score_above_100():
    with pytest.raises(ValidationError):
        GradingResult(
            submission_id=VALID_SUBMISSION_ID,
            code_score=100.1,
            vision_score=90.0,
            final_score=95.0,
        )


def test_invalid_data_score_below_zero():
    with pytest.raises(ValidationError):
        GradingResult(
            submission_id=VALID_SUBMISSION_ID,
            code_score=80.0,
            data_score=-0.5,
            vision_score=90.0,
            final_score=80.0,
        )


def test_invalid_data_score_above_100():
    with pytest.raises(ValidationError):
        GradingResult(
            submission_id=VALID_SUBMISSION_ID,
            code_score=80.0,
            data_score=105.0,
            vision_score=90.0,
            final_score=80.0,
        )


def test_invalid_vision_score_below_zero():
    with pytest.raises(ValidationError):
        GradingResult(
            submission_id=VALID_SUBMISSION_ID,
            code_score=80.0,
            vision_score=-1.0,
            final_score=80.0,
        )


def test_invalid_vision_score_above_100():
    with pytest.raises(ValidationError):
        GradingResult(
            submission_id=VALID_SUBMISSION_ID,
            code_score=80.0,
            vision_score=101.0,
            final_score=80.0,
        )


def test_invalid_final_score_below_zero():
    with pytest.raises(ValidationError):
        GradingResult(
            submission_id=VALID_SUBMISSION_ID,
            code_score=80.0,
            vision_score=90.0,
            final_score=-0.1,
        )


def test_invalid_final_score_above_100():
    with pytest.raises(ValidationError):
        GradingResult(
            submission_id=VALID_SUBMISSION_ID,
            code_score=80.0,
            vision_score=90.0,
            final_score=100.5,
        )
