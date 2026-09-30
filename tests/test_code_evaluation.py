import pytest
from pydantic import ValidationError

from ai_grading_iot.schemas.code_evaluation import CodeEvaluation, CriterionResult


def test_valid_code_evaluation():
    eval_result = CodeEvaluation(
        criteria_results=[
            CriterionResult(
                criterion="Đọc cảm biến DHT22",
                score=85.0,
                feedback="Code đọc đúng chân dữ liệu, có kiểm tra null",
            ),
            CriterionResult(
                criterion="Điều khiển LED cảnh báo",
                score=90.0,
                feedback="Bật tắt đúng ngưỡng nhiệt độ",
            ),
        ],
        code_score=87.5,
        overall_feedback="Bài làm tốt, cấu trúc rõ ràng",
    )

    assert len(eval_result.criteria_results) == 2
    assert eval_result.criteria_results[0].score == 85.0
    assert eval_result.code_score == 87.5


def test_boundary_scores_valid():
    eval_result = CodeEvaluation(
        criteria_results=[
            CriterionResult(criterion="Tiêu chí 0 điểm", score=0.0, feedback="Không làm"),
            CriterionResult(criterion="Tiêu chí 100 điểm", score=100.0, feedback="Hoàn hảo"),
        ],
        code_score=100.0,
        overall_feedback="Kiểm tra biên hợp lệ",
    )
    assert eval_result.criteria_results[0].score == 0.0
    assert eval_result.criteria_results[1].score == 100.0
    assert eval_result.code_score == 100.0


def test_empty_criteria_results_fails():
    with pytest.raises(ValidationError):
        CodeEvaluation(
            criteria_results=[],
            code_score=80.0,
            overall_feedback="Không có tiêu chí",
        )


def test_criterion_score_negative_fails():
    with pytest.raises(ValidationError):
        CriterionResult(
            criterion="Tiêu chí",
            score=-1.0,
            feedback="Điểm âm",
        )


def test_criterion_score_above_100_fails():
    with pytest.raises(ValidationError):
        CriterionResult(
            criterion="Tiêu chí",
            score=100.5,
            feedback="Điểm vượt 100",
        )


def test_code_score_negative_fails():
    with pytest.raises(ValidationError):
        CodeEvaluation(
            criteria_results=[
                CriterionResult(criterion="T1", score=80.0, feedback="OK")
            ],
            code_score=-0.5,
            overall_feedback="Tổng điểm âm",
        )


def test_code_score_above_100_fails():
    with pytest.raises(ValidationError):
        CodeEvaluation(
            criteria_results=[
                CriterionResult(criterion="T1", score=80.0, feedback="OK")
            ],
            code_score=105.0,
            overall_feedback="Tổng điểm vượt 100",
        )


def test_invalid_data_types():
    with pytest.raises(ValidationError):
        CodeEvaluation(
            criteria_results="not-a-list",  # type: ignore
            code_score="invalid-score",  # type: ignore
            overall_feedback=12345,  # type: ignore
        )
