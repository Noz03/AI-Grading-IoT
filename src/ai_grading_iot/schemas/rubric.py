from enum import Enum
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class RubricType(str, Enum):
    CODE = "code"
    DATA = "data"
    VISION = "vision"


class Rubric(BaseModel):
    id: UUID = Field(default_factory=uuid4, description="Định danh duy nhất dạng UUID")
    type: RubricType = Field(..., description="Phân loại rubric: code, data, hoặc vision")
    weight: float = Field(
        ...,
        ge=0,
        le=100,
        description="Trọng số đóng góp vào tổng điểm, giới hạn trong đoạn [0, 100]",
    )
    criteria: list[str] = Field(
        ...,
        min_length=1,
        description="Danh sách các tiêu chí đánh giá, tối thiểu 1 tiêu chí",
    )
