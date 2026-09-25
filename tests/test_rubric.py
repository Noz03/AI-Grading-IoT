from uuid import UUID
import pytest
from pydantic import ValidationError

from ai_grading_iot.schemas.rubric import Rubric, RubricType


def test_create_code_rubric():
    rubric = Rubric(
        type=RubricType.CODE,
        weight=70.0,
        criteria=[
            "Đọc đúng dữ liệu cảm biến.",
            "Xử lý dữ liệu đúng yêu cầu.",
        ],
    )

    assert isinstance(rubric.id, UUID)
    assert rubric.type == RubricType.CODE
    assert rubric.weight == 70.0
    assert len(rubric.criteria) == 2


def test_create_data_rubric():
    rubric = Rubric(
        type=RubricType.DATA,
        weight=10.0,
        criteria=["Giá trị cảm biến được cập nhật đúng."],
    )

    assert isinstance(rubric.id, UUID)
    assert rubric.type == RubricType.DATA
    assert rubric.weight == 10.0
    assert rubric.criteria == ["Giá trị cảm biến được cập nhật đúng."]


def test_create_vision_rubric():
    rubric = Rubric(
        type=RubricType.VISION,
        weight=20.0,
        criteria=[
            "Các linh kiện được lắp đúng vị trí.",
            "Dây nối được kết nối đúng.",
        ],
    )

    assert isinstance(rubric.id, UUID)
    assert rubric.type == RubricType.VISION
    assert rubric.weight == 20.0
    assert len(rubric.criteria) == 2


def test_weight_boundaries_valid():
    min_rubric = Rubric(
        type=RubricType.CODE,
        weight=0.0,
        criteria=["Tiêu chí kiểm thử biên 0."],
    )
    max_rubric = Rubric(
        type=RubricType.CODE,
        weight=100.0,
        criteria=["Tiêu chí kiểm thử biên 100."],
    )

    assert min_rubric.weight == 0.0
    assert max_rubric.weight == 100.0


def test_weight_cannot_be_negative():
    with pytest.raises(ValidationError):
        Rubric(
            type=RubricType.CODE,
            weight=-1.0,
            criteria=["Chương trình hoạt động đúng."],
        )


def test_weight_cannot_exceed_100():
    with pytest.raises(ValidationError):
        Rubric(
            type=RubricType.CODE,
            weight=100.5,
            criteria=["Chương trình hoạt động đúng."],
        )


def test_criteria_cannot_be_empty():
    with pytest.raises(ValidationError):
        Rubric(
            type=RubricType.CODE,
            weight=70.0,
            criteria=[],
        )


def test_invalid_rubric_type():
    with pytest.raises(ValidationError):
        Rubric(
            type="hardware",  # type: ignore
            weight=20.0,
            criteria=["Kiểm tra phần cứng."],
        )
