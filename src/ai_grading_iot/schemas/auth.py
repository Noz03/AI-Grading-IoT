from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from ai_grading_iot.schemas.user import UserInput, normalize_email


class RegisterRequest(UserInput):
    pass


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def clean_email(cls, value: str) -> str:
        return normalize_email(value) if isinstance(value, str) else value


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
