from enum import Enum
from decimal import Decimal
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
        description="Danh sách tiêu chí; loại không áp dụng có thể rỗng",
    )

    @field_validator("weight")
    @classmethod
    def valid_precision(cls, value: float) -> float:
        if Decimal(str(value)).as_tuple().exponent < -2:
            raise ValueError("Weight supports at most two decimal places")
        return value

    @field_validator("criteria")
    @classmethod
    def valid_criteria(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("Criteria must contain meaningful text")
        return value

    @model_validator(mode="after")
    def positive_weight_has_criteria(self):
        if self.weight > 0 and not self.criteria:
            raise ValueError("Positive-weight rubric requires criteria")
        return self


class RubricUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weight: float | None = Field(default=None, ge=0, le=100)
    criteria: list[str] | None = None

    @field_validator("weight")
    @classmethod
    def valid_precision(cls, value: float | None) -> float | None:
        if value is not None and Decimal(str(value)).as_tuple().exponent < -2:
            raise ValueError("Weight supports at most two decimal places")
        return value


class RubricDetail(Rubric):
    practice_id: UUID
