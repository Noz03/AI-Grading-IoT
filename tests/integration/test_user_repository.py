
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from ai_grading_iot.db.session import get_engine
from ai_grading_iot.repositories.user_repository import UserRepository

from sqlalchemy import select
from ai_grading_iot.models.user import User

@pytest.fixture
def db_session():
    engine = get_engine()

    with engine.connect() as connection:
        transaction = connection.begin()

        with Session(
            bind=connection,
            autoflush=False,
            expire_on_commit=False,
        ) as session:
            try:
                yield session
            finally:
                session.close()
                transaction.rollback()


@pytest.fixture
def repository(db_session):
    return UserRepository(db_session)


def make_user(repository, role="student"):
    unique_email = f"user_{uuid4().hex}@example.com"

    return repository.create(
        email=unique_email,
        password_hash="fake_hash_for_testing",
        full_name="Test User",
        role=role,
    )


def test_create_user(repository):
    user = make_user(repository)

    assert user.id is not None
    assert user.email.endswith("@example.com")
    assert user.role == "student"
    assert user.is_active is True


def test_get_user_by_id(repository):
    user = make_user(repository)

    found = repository.get_by_id(user.id)

    assert found is not None
    assert found.id == user.id


def test_get_user_by_email(repository):
    user = make_user(repository)

    found = repository.get_by_email(user.email)

    assert found is not None
    assert found.email == user.email


def test_get_nonexistent_user(repository):
    found = repository.get_by_id(uuid4())

    assert found is None


def test_get_all_users(repository):
    make_user(repository)
    make_user(repository)

    users = repository.get_all(limit=100)

    assert len(users) >= 2


def test_get_users_by_role(repository):
    make_user(repository, role="student")
    make_user(repository, role="teacher")

    students = repository.get_by_role("student")

    assert any(user.role == "student" for user in students)


def test_update_user(repository):
    user = make_user(repository)

    updated = repository.update(
        user,
        full_name="Updated Name",
        is_active=False,
    )

    assert updated.full_name == "Updated Name"
    assert updated.is_active is False


def test_delete_user(repository):
    user = make_user(repository)
    user_id = user.id

    repository.delete(user)

    assert repository.get_by_id(user_id) is None


def test_pagination_validation(repository):
    with pytest.raises(ValueError):
        repository.get_all(limit=0)

    with pytest.raises(ValueError):
        repository.get_all(limit=101)

    with pytest.raises(ValueError):
        repository.get_all(offset=-1)


def test_user_persisted_in_transaction(db_session):
    repository = UserRepository(db_session)

    user = make_user(repository)

    statement = select(User).where(
        User.id == user.id
    )

    found = db_session.scalar(statement)

    assert found is not None
    assert found.email == user.email