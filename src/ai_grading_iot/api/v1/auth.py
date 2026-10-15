from fastapi import APIRouter, HTTPException

from ai_grading_iot.api.dependencies import CurrentUser, DBSession
from ai_grading_iot.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from ai_grading_iot.schemas.user import UserResponse
from ai_grading_iot.services.auth_service import (
    AuthService, InactiveUserError, InvalidCredentialsError,
)
from ai_grading_iot.services.user_service import DuplicateEmailError


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=201)
def register(data: RegisterRequest, db: DBSession):
    try:
        return AuthService(db).register(data)
    except DuplicateEmailError as exc:
        raise HTTPException(status_code=409, detail="Email already registered") from exc


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: DBSession):
    try:
        return AuthService(db).login(data)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except InactiveUserError as exc:
        raise HTTPException(status_code=403, detail="Inactive user") from exc


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser):
    return user
