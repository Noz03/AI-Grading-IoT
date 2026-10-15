from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ai_grading_iot.api.dependencies import DBSession, require_roles
from ai_grading_iot.models.user import User
from ai_grading_iot.schemas.user import UserCreate, UserResponse, UserStatusUpdate
from ai_grading_iot.services.user_service import (
    DuplicateEmailError, UserNotFoundError, UserService, UserStatusError,
)


router = APIRouter(prefix="/users", tags=["Users"])
AdminUser = Annotated[User, Depends(require_roles("admin"))]


@router.post("", response_model=UserResponse, status_code=201)
def create_user(data: UserCreate, db: DBSession, admin: AdminUser):
    try:
        return UserService(db).create_user(data)
    except DuplicateEmailError as exc:
        raise HTTPException(status_code=409, detail="Email already registered") from exc


@router.get("", response_model=list[UserResponse])
def list_users(
    db: DBSession,
    admin: AdminUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return UserService(db).list_users(limit=limit, offset=offset)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: UUID, db: DBSession, admin: AdminUser):
    try:
        return UserService(db).get_user(user_id)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc


@router.patch("/{user_id}/status", response_model=UserResponse)
def update_status(
    user_id: UUID, data: UserStatusUpdate, db: DBSession, admin: AdminUser,
):
    try:
        return UserService(db).update_status(user_id, data.is_active, admin)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
    except UserStatusError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
