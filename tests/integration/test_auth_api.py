from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ai_grading_iot.core.config import get_settings
from ai_grading_iot.core.security import hash_password
from ai_grading_iot.db.session import get_db, get_engine
from ai_grading_iot.main import app
from ai_grading_iot.repositories.user_repository import UserRepository


@pytest.fixture
def auth_client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "integration-test-key-at-least-thirty-two-bytes")
    get_settings.cache_clear()
    with get_engine().connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint",
                     autoflush=False, expire_on_commit=False) as session:
            def fake_get_db():
                yield session

            app.dependency_overrides[get_db] = fake_get_db
            try:
                yield TestClient(app), session
            finally:
                app.dependency_overrides.clear()
                session.close()
                transaction.rollback()
    get_settings.cache_clear()


def test_register_login_and_admin_management(auth_client):
    client, db = auth_client
    email = f"student-{uuid4().hex}@example.com"
    response = client.post("/api/v1/auth/register", json={
        "email": email.upper(), "password": "123456", "full_name": "Student",
    })
    assert response.status_code == 201
    assert response.json()["email"] == email
    stored = UserRepository(db).get_by_email(email)
    assert stored is not None and stored.password_hash != "123456"
    assert client.post("/api/v1/auth/register", json={
        "email": email, "password": "123456", "full_name": "Student",
    }).status_code == 409
    login = client.post("/api/v1/auth/login", json={
        "email": email, "password": "123456",
    })
    assert login.status_code == 200
    assert login.json()["expires_in"] == 1800
    student_token = login.json()["access_token"]
    assert client.get("/api/v1/auth/me", headers={
        "Authorization": f"Bearer {student_token}",
    }).json()["id"] == str(stored.id)
    assert client.get("/api/v1/users", headers={
        "Authorization": f"Bearer {student_token}",
    }).status_code == 403

    admin_email = f"admin-{uuid4().hex}@example.com"
    admin = UserRepository(db).create(
        email=admin_email, password_hash=hash_password("secret6"),
        full_name="Admin", role="admin",
    )
    db.commit()
    admin_token = client.post("/api/v1/auth/login", json={
        "email": admin_email, "password": "secret6",
    }).json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}
    assert client.get(f"/api/v1/users/{stored.id}", headers=headers).status_code == 200
    assert client.patch(f"/api/v1/users/{admin.id}/status", headers=headers,
                        json={"is_active": False}).status_code == 409
    assert client.patch(f"/api/v1/users/{stored.id}/status", headers=headers,
                        json={"is_active": False}).status_code == 200
    assert client.get("/api/v1/auth/me", headers={
        "Authorization": f"Bearer {student_token}",
    }).status_code == 403

    # Simulate two registrations that both passed the initial availability check.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(UserRepository, "get_by_email", lambda self, value: None)
        conflict = client.post("/api/v1/auth/register", json={
            "email": email, "password": "123456", "full_name": "Student",
        })
    assert conflict.status_code == 409
