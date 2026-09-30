import json
from uuid import UUID
import pytest

from ai_grading_iot.clients.llm_client import LLMClient
from ai_grading_iot.graders.code_grader import CodeGrader
from ai_grading_iot.schemas.practice import (
    Practice,
    PracticeEnvironment,
    PracticeMetadata,
    PracticeRequirements,
    PracticeRubricReference,
    PracticeTask,
)
from ai_grading_iot.schemas.rubric import Rubric, RubricType
from ai_grading_iot.schemas.submission import Submission


class MockLLMClient(LLMClient):
    """Mock LLM Client giả lập phản hồi của LLM trong unit tests."""

    def __init__(self, response_text: str = "", raise_error: bool = False):
        self.response_text = response_text
        self.raise_error = raise_error

    def generate(self, prompt: str) -> str:
        if self.raise_error:
            raise RuntimeError("LLM Connection Failed")
        return self.response_text


@pytest.fixture
def sample_practice():
    return Practice(
        practice_id=UUID("00000000-0000-0000-0000-000000000003"),
        title="ESP32 LED Control",
        description="Điều khiển LED bằng ESP32",
        requirements=PracticeRequirements(
            objective="Điều khiển LED chớp tắt",
            tasks=[
                PracticeTask(
                    id=UUID("00000000-0000-0000-0000-000000000001"),
                    order=1,
                    description="Viết hàm setup và loop điều khiển LED",
                )
            ],
            constraints=["Dùng Arduino C++"],
        ),
        environment=PracticeEnvironment(
            board="ESP32",
            framework="Arduino",
            language="C++",
            libraries=[],
        ),
        hardware=[],
        rubric=PracticeRubricReference(
            code_rubric_id=UUID("00000000-0000-0000-0000-000000000002")
        ),
        metadata=PracticeMetadata(created_by="teacher-001"),
    )


@pytest.fixture
def sample_rubric():
    return Rubric(
        type=RubricType.CODE,
        weight=70.0,
        criteria=[
            "Cấu hình đúng GPIO Output cho LED",
            "Logic chớp tắt delay chính xác",
        ],
    )


@pytest.fixture
def sample_submission():
    return Submission(
        practice_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        student_id=UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8"),
        description="Bài làm nộp",
        code="void setup() { pinMode(2, OUTPUT); } void loop() { digitalWrite(2, HIGH); delay(1000); }",
        images=[],
    )


# Trường hợp 1: Code hợp lệ -> tính điểm đúng
def test_code_grader_success(sample_practice, sample_rubric, sample_submission):
    mock_response = {
        "criteria_results": [
            {
                "criterion": "Cấu hình đúng GPIO Output cho LED",
                "score": 90.0,
                "feedback": "Cấu hình pinMode đúng",
            },
            {
                "criterion": "Logic chớp tắt delay chính xác",
                "score": 80.0,
                "feedback": "Logic đúng nhưng thiếu turn off",
            },
        ],
        "code_score": 85.0,
        "overall_feedback": "Bài làm tốt",
    }

    mock_client = MockLLMClient(response_text=json.dumps(mock_response))
    grader = CodeGrader(llm_client=mock_client)

    grading_result, evaluation = grader.grade(
        sample_practice, sample_rubric, sample_submission
    )

    # (90 + 80) / 2 = 85.0
    assert grading_result.code_score == 85.0
    assert grading_result.submission_id == sample_submission.id
    assert len(evaluation.criteria_results) == 2


# Trường hợp 2: Sai loại Rubric -> reject
def test_code_grader_rejects_non_code_rubric(sample_practice, sample_submission):
    data_rubric = Rubric(
        type=RubricType.DATA,
        weight=20.0,
        criteria=["Định dạng dữ liệu hợp lệ"],
    )
    grader = CodeGrader(llm_client=MockLLMClient())

    with pytest.raises(ValueError, match="RubricType.CODE"):
        grader.grade(sample_practice, data_rubric, sample_submission)


# Trường hợp 3: Không có code hoặc code rỗng -> reject
def test_code_grader_rejects_empty_code(sample_practice, sample_rubric):
    empty_submission = Submission(
        practice_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        student_id=UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8"),
        description="Không nộp code",
        code="   ",
        images=[],
    )
    grader = CodeGrader(llm_client=MockLLMClient())

    with pytest.raises(ValueError, match="không được để trống"):
        grader.grade(sample_practice, sample_rubric, empty_submission)


# Trường hợp 4: LLM trả thiếu criterion -> reject
def test_code_grader_fails_when_criterion_missing(
    sample_practice, sample_rubric, sample_submission
):
    incomplete_response = {
        "criteria_results": [
            {
                "criterion": "Cấu hình đúng GPIO Output cho LED",
                "score": 90.0,
                "feedback": "Cấu hình đúng",
            }
        ],
        "code_score": 90.0,
        "overall_feedback": "Thiếu đánh giá delay",
    }
    mock_client = MockLLMClient(response_text=json.dumps(incomplete_response))
    grader = CodeGrader(llm_client=mock_client)

    with pytest.raises(ValueError, match="thiếu tiêu chí đánh giá"):
        grader.grade(sample_practice, sample_rubric, sample_submission)


# Trường hợp 5: Score ngoài phạm vi -> reject
def test_code_grader_score_out_of_range(
    sample_practice, sample_rubric, sample_submission
):
    invalid_score_response = {
        "criteria_results": [
            {
                "criterion": "Cấu hình đúng GPIO Output cho LED",
                "score": 120.0,  # Vượt quá 100
                "feedback": "Quá tốt",
            },
            {
                "criterion": "Logic chớp tắt delay chính xác",
                "score": 80.0,
                "feedback": "OK",
            },
        ],
        "code_score": 100.0,
        "overall_feedback": "Test",
    }
    mock_client = MockLLMClient(response_text=json.dumps(invalid_score_response))
    grader = CodeGrader(llm_client=mock_client)

    with pytest.raises(ValueError):
        grader.grade(sample_practice, sample_rubric, sample_submission)


# Trường hợp 6: Kiểm tra công thức Weighted score
def test_code_grader_weighted_score_calculation(
    sample_practice, sample_rubric, sample_submission
):
    mock_response = {
        "criteria_results": [
            {
                "criterion": "Cấu hình đúng GPIO Output cho LED",
                "score": 100.0,
                "feedback": "Đạt",
            },
            {
                "criterion": "Logic chớp tắt delay chính xác",
                "score": 50.0,
                "feedback": "Chưa hoàn chỉnh",
            },
        ],
        "code_score": 75.0,
        "overall_feedback": "Đạt 75%",
    }
    mock_client = MockLLMClient(response_text=json.dumps(mock_response))
    grader = CodeGrader(llm_client=mock_client)

    grading_result, _ = grader.grade(
        sample_practice, sample_rubric, sample_submission
    )

    # (100 + 50) / 2 = 75.0
    assert grading_result.code_score == 75.0
    assert grading_result.final_score == 75.0


# Trường hợp 7: LLM failure -> raise RuntimeError, không biến thành điểm 0
def test_code_grader_llm_failure(
    sample_practice, sample_rubric, sample_submission
):
    mock_client = MockLLMClient(raise_error=True)
    grader = CodeGrader(llm_client=mock_client)

    with pytest.raises(RuntimeError, match="Lỗi khi gọi LLM Client"):
        grader.grade(sample_practice, sample_rubric, sample_submission)
