import json
import math
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Measurement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    value: float
    unit: str | None = Field(default=None, max_length=32)

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Measurement name cannot be blank")
        return value

    @field_validator("value", mode="before")
    @classmethod
    def numeric_value(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("Measurement value must be a finite number")
        return value


class DashboardEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str | None = Field(default=None, max_length=2000)
    image_ids: list[UUID] = Field(default_factory=list, max_length=5)


class DataEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    measurements: list[Measurement] = Field(default_factory=list, max_length=100)
    dashboard: DashboardEvidence | None = None
    notes: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def size_limit(self):
        if len(json.dumps(self.model_dump(mode="json"), ensure_ascii=False).encode()) > 65536:
            raise ValueError("Data evidence exceeds 64 KiB")
        return self
