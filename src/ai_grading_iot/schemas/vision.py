"""Validated detector output and multimodal evaluation contracts."""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BoundingBox(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x1: float
    y1: float
    x2: float
    y2: float


class Detection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    class_id: int = Field(ge=0)
    class_name: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    bbox: BoundingBox


class ImageDetections(BaseModel):
    model_config = ConfigDict(extra="forbid")
    image_id: UUID
    image_width: int = Field(gt=0)
    image_height: int = Field(gt=0)
    model_version: str = Field(min_length=1)
    detections: list[Detection]

    @model_validator(mode="after")
    def coordinates_inside_image(self):
        for item in self.detections:
            box = item.bbox
            if not (0 <= box.x1 < box.x2 <= self.image_width and
                    0 <= box.y1 < box.y2 <= self.image_height):
                raise ValueError("Detection bbox is outside the original image")
        return self


Status = Literal["observed", "not_observed", "uncertain", "not_applicable"]


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    criterion: str
    status: Status
    evidence: str = Field(min_length=1)


class ImageEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    image_id: UUID
    observations: list[Observation]
    limitations: list[str] = Field(default_factory=list)


class CriterionFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")
    criterion: str
    status: Status
    feedback: str = Field(min_length=1)
    image_ids: list[UUID]


class AggregateEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    score: float | None = Field(ge=0, le=100, allow_inf_nan=False)
    evidence_status: Literal["sufficient", "insufficient"]
    feedback: str = Field(min_length=1)
    criteria_feedback: list[CriterionFeedback]

    @model_validator(mode="after")
    def score_matches_evidence(self):
        if (self.evidence_status == "sufficient") != (self.score is not None):
            raise ValueError("Score must be present exactly when evidence is sufficient")
        return self


class VisionResult(BaseModel):
    vision_score: float | None
    vision_evaluation: dict
    graded_at: str | None = None
