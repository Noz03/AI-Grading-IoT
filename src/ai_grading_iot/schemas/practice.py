from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PracticeStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class PracticeTask(BaseModel):
    id: UUID = Field(
        default_factory=uuid4,
        description="ID task tự động sinh bằng UUID",
    )
    order: int = Field(
        ...,
        ge=1,
        description="Thứ tự của task trong bài thực hành",
    )
    description: str = Field(..., min_length=1)


class PracticeRequirements(BaseModel):
    objective: str = Field(..., min_length=1)
    tasks: list[PracticeTask] = Field(..., min_length=1)
    constraints: list[str] = Field(default_factory=list)


class PracticeEnvironment(BaseModel):
    board: str = Field(
        ...,
        min_length=1,
        description="Ví dụ: ESP32, STM32F4",
    )
    framework: str = Field(
        ...,
        min_length=1,
        description="Ví dụ: Arduino, ESP-IDF",
    )
    language: str = Field(
        ...,
        min_length=1,
        description="Ví dụ: C++, MicroPython",
    )
    libraries: list[str] = Field(default_factory=list)


class PracticeHardware(BaseModel):
    id: UUID = Field(
        default_factory=uuid4,
        description="ID phần cứng tự động sinh bằng UUID",
    )
    name: str = Field(..., min_length=1)
    type: str = Field(
        ...,
        min_length=1,
        description="microcontroller, sensor, actuator, etc.",
    )


class PracticeRubricReference(BaseModel):
    code_rubric_id: UUID | None = None
    dashboard_rubric_id: UUID | None = None
    vision_rubric_id: UUID | None = None


class PracticeMetadata(BaseModel):
    created_by: str = Field(..., min_length=1)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class Practice(BaseModel):
    practice_id: UUID = Field(
        default_factory=uuid4,
        description="ID bài thực hành tự động sinh bằng UUID",
    )

    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)

    requirements: PracticeRequirements
    environment: PracticeEnvironment
    hardware: list[PracticeHardware] = Field(default_factory=list)

    rubric: PracticeRubricReference

    version: str = Field(
        default="1.0",
        pattern=r"^\d+\.\d+(\.\d+)?$",
    )

    status: PracticeStatus = Field(
        default=PracticeStatus.DRAFT
    )

    metadata: PracticeMetadata
