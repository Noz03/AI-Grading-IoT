from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_grading_iot.core.security import hash_password
from ai_grading_iot.models.user import User
from ai_grading_iot.repositories.user_repository import UserRepository
from ai_grading_iot.schemas.user import UserCreate


class DuplicateEmailError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class UserStatusError(Exception):
    pass


class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = UserRepository(db)

    def create_user(self, data: UserCreate) -> User:
        if self.repository.get_by_email(str(data.email)):
            raise DuplicateEmailError
        try:
            user = self.repository.create(
                email=str(data.email),
                password_hash=hash_password(data.password),
                full_name=data.full_name,
                role=data.role.value,
            )
            self.db.commit()
            return user
        except IntegrityError as exc:
            self.db.rollback()
            if getattr(getattr(exc.orig, "diag", None), "constraint_name", None) == "ix_users_email":
                raise DuplicateEmailError from exc
            raise
        except Exception:
            self.db.rollback()
            raise

    def list_users(self, *, limit: int, offset: int) -> list[User]:
        return self.repository.get_all(limit=limit, offset=offset)

    def get_user(self, user_id: UUID) -> User:
        user = self.repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError
        return user

    def update_status(self, user_id: UUID, is_active: bool, actor: User) -> User:
        try:
            user = self.get_user(user_id)
            if user.is_active and not is_active and user.role == "admin":
                if user.id == actor.id:
                    raise UserStatusError("Không thể vô hiệu hóa tài khoản của chính mình.")
                active_admins = self.repository.get_active_admins_for_update()
                if len(active_admins) <= 1:
                    raise UserStatusError("Không thể vô hiệu hóa Admin hoạt động cuối cùng.")
            user = self.repository.update(user, is_active=is_active)
            self.db.commit()
            return user
        except Exception:
            self.db.rollback()
            raise
