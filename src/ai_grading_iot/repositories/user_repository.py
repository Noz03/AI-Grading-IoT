
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_grading_iot.models.user import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        email: str,
        password_hash: str,
        full_name: str,
        role: str,
    ) -> User:
        user = User(
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            role=role,
        )

        self.db.add(user)
        self.db.flush()

        return user

    def get_by_id(self, user_id: UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        statement = select(User).where(
            User.email == email
        )

        return self.db.scalar(statement)

    def get_all(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[User]:
        if limit < 1 or limit > 100:
            raise ValueError("limit phải nằm trong khoảng 1–100")

        if offset < 0:
            raise ValueError("offset không được âm")

        statement = (
            select(User)
            .order_by(User.created_at, User.id)
            .limit(limit)
            .offset(offset)
        )

        return list(self.db.scalars(statement).all())

    def get_by_role(self, role: str) -> list[User]:
        statement = (
            select(User)
            .where(User.role == role)
            .order_by(User.created_at, User.id)
        )

        return list(self.db.scalars(statement).all())

    def update(
        self,
        user: User,
        *,
        full_name: str | None = None,
        is_active: bool | None = None,
    ) -> User:
        if full_name is not None:
            user.full_name = full_name

        if is_active is not None:
            user.is_active = is_active

        self.db.flush()

        return user

    def delete(self, user: User) -> None:
        self.db.delete(user)
        self.db.flush()
