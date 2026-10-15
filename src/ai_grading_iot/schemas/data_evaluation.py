from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DataCriterionFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")
    criterion: str = Field(min_length=1)
    feedback: str = Field(min_length=1)


class DataEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    score: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    feedback: str = Field(min_length=1)
    criteria_feedback: list[DataCriterionFeedback]
    evidence_status: Literal["sufficient", "insufficient"]

    @model_validator(mode="after")
    def consistent_score(self):
        if (self.evidence_status == "sufficient") != (self.score is not None):
            raise ValueError("Data score and evidence status disagree")
        return self
