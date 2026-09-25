from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class GradingResult(BaseModel):
    id: UUID = Field(
        default_factory=uuid4,
        description="Định danh duy nhất của GradingResult",
    )

    submission_id: UUID = Field(
        ...,
        description="Định danh Submission được chấm",
    )

    code_score: float = Field(
        ...,
        ge=0,
        le=100,
        description="Điểm đánh giá phần code",
    )

    data_score: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Điểm đánh giá phần data/dashboard nếu Practice có yêu cầu",
    )

    vision_score: float = Field(
        ...,
        ge=0,
        le=100,
        description="Điểm đánh giá hình ảnh kit",
    )

    final_score: float = Field(
        ...,
        ge=0,
        le=100,
        description="Điểm tổng hợp cuối cùng",
        )
