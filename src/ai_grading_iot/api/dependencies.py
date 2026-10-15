from typing import Annotated

from fastapi import Depends
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ai_grading_iot.clients.groq_client import GroqClient
from ai_grading_iot.db.session import get_db
from ai_grading_iot.graders.code_grader import CodeGrader
from ai_grading_iot.graders.rubric_generator import RubricGenerator
from ai_grading_iot.core.security import decode_access_token
from ai_grading_iot.models.user import User
from ai_grading_iot.repositories.user_repository import UserRepository


DBSession = Annotated[
    Session,
    Depends(get_db),
]

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    db: DBSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or missing authentication token")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Inactive user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: str):
    def check_roles(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return check_roles


def get_code_grader() -> CodeGrader:
    llm_client = GroqClient()

    return CodeGrader(
        llm_client=llm_client
    )


def get_rubric_generator() -> RubricGenerator:
    return RubricGenerator()
