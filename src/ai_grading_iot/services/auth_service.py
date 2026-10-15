from sqlalchemy.orm import Session

from ai_grading_iot.core.security import create_access_token, verify_password
from ai_grading_iot.models.user import User
from ai_grading_iot.repositories.user_repository import UserRepository
from ai_grading_iot.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from ai_grading_iot.schemas.user import UserCreate, UserRole
from ai_grading_iot.services.user_service import UserService


class InvalidCredentialsError(Exception):
    pass


class InactiveUserError(Exception):
    pass


class AuthService:
    def __init__(self, db: Session):
        self.users = UserRepository(db)
        self.user_service = UserService(db)

    def register(self, data: RegisterRequest) -> User:
        return self.user_service.create_user(
            UserCreate(**data.model_dump(), role=UserRole.STUDENT)
        )

    def login(self, data: LoginRequest) -> TokenResponse:
        user = self.users.get_by_email(str(data.email))
        if user is None or not verify_password(data.password, user.password_hash):
            raise InvalidCredentialsError
        if not user.is_active:
            raise InactiveUserError
        token, expires_in = create_access_token(user.id)
        return TokenResponse(access_token=token, expires_in=expires_in)
