import os

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from ai_grading_iot.core.security import hash_password
from ai_grading_iot.db.session import get_session_factory
from ai_grading_iot.repositories.user_repository import UserRepository
from ai_grading_iot.schemas.user import UserCreate, UserRole


def seed_admin() -> bool:
    names = ("SEED_ADMIN_EMAIL", "SEED_ADMIN_FULL_NAME", "SEED_ADMIN_PASSWORD")
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        raise ValueError("Missing required environment variables: " + ", ".join(missing))
    try:
        data = UserCreate(
            email=os.environ["SEED_ADMIN_EMAIL"],
            full_name=os.environ["SEED_ADMIN_FULL_NAME"],
            password=os.environ["SEED_ADMIN_PASSWORD"],
            role=UserRole.ADMIN,
        )
    except ValidationError as exc:
        raise ValueError("Invalid seed admin email, name, or password") from exc

    with get_session_factory()() as db:
        try:
            repository = UserRepository(db)
            existing = repository.get_by_email(str(data.email))
            if existing is not None:
                if existing.role != "admin":
                    raise ValueError("Seed email belongs to a non-Admin user")
                return False
            repository.create(
                email=str(data.email),
                full_name=data.full_name,
                password_hash=hash_password(data.password),
                role="admin",
            )
            db.commit()
            return True
        except IntegrityError as exc:
            db.rollback()
            raise ValueError("Seed email already exists") from exc
        except Exception:
            db.rollback()
            raise


def main() -> None:
    try:
        created = seed_admin()
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print("Admin account created." if created else "Admin account already exists.")


if __name__ == "__main__":
    main()
