from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def normalize_code(value: str) -> str:
    return value.strip().upper()


def nonblank_name(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Course name cannot be blank")
    return cleaned


class CourseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None

    @field_validator("code", mode="before")
    @classmethod
    def normalized_code(cls, value: str) -> str:
        return normalize_code(value) if isinstance(value, str) else value

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        return nonblank_name(value)


class CourseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str | None) -> str | None:
        return nonblank_name(value) if value is not None else value


class CourseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None


class CourseJoin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course_code: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("course_code", mode="before")
    @classmethod
    def normalized_code(cls, value: str) -> str:
        return normalize_code(value) if isinstance(value, str) else value


class TeacherAssignment(BaseModel):
    teacher_id: UUID


class StudentEnrollment(BaseModel):
    student_id: UUID


class MembershipResponse(BaseModel):
    course_id: UUID
    user_id: UUID
