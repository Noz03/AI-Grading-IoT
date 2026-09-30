from pydantic import BaseModel, Field


class CriterionResult(BaseModel):
    criterion: str = Field(
        ...,
        min_length=1,
        description="Nội dung tiêu chí được đánh giá",
    )
    score: float = Field(
        ...,
        ge=0,
        le=100,
        description="Điểm đánh giá cho tiêu chí từ 0 đến 100",
    )
    feedback: str = Field(
        ...,
        min_length=1,
        description="Giải thích lý do cho điểm của tiêu chí",
    )


class CodeEvaluation(BaseModel):
    criteria_results: list[CriterionResult] = Field(
        ...,
        min_length=1,
        description="Danh sách kết quả đánh giá cho từng tiêu chí, tối thiểu 1 tiêu chí",
    )
    code_score: float = Field(
        ...,
        ge=0,
        le=100,
        description="Điểm tổng quan phần code do LLM đề xuất",
    )
    overall_feedback: str = Field(
        ...,
        min_length=1,
        description="Nhận xét tổng quan về toàn bộ bài code",
    )
