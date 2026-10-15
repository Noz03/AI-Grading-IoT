from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from ai_grading_iot.core.config import get_settings
from ai_grading_iot.core.security import (
    create_access_token, decode_access_token, hash_password, verify_password,
)
from ai_grading_iot.db.session import get_db
from ai_grading_iot.main import app
from ai_grading_iot.repositories.user_repository import UserRepository
from ai_grading_iot.scripts import seed_admin
from ai_grading_iot.services.user_service import UserService, UserStatusError


SECRET = "test-only-secret-at-least-thirty-two-bytes-long"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", SECRET)
    get_settings.cache_clear()
    users = {}
    db = Mock()

    def fake_get_db():
        yield db

    def get_by_email(self, email):
        return users.get(email)

    def get_by_id(self, user_id):
        return next((u for u in users.values() if u.id == user_id), None)

    def create(self, *, email, password_hash, full_name, role):
        user = SimpleNamespace(
            id=uuid4(), email=email, password_hash=password_hash,
            full_name=full_name, role=role, is_active=True,
        )
        users[email] = user
        return user

    def get_all(self, *, limit=20, offset=0):
        return list(users.values())[offset:offset + limit]

    def update(self, user, *, full_name=None, is_active=None):
        if is_active is not None:
            user.is_active = is_active
        return user

    monkeypatch.setattr(UserRepository, "get_by_email", get_by_email)
    monkeypatch.setattr(UserRepository, "get_by_id", get_by_id)
    monkeypatch.setattr(UserRepository, "create", create)
    monkeypatch.setattr(UserRepository, "get_all", get_all)
    monkeypatch.setattr(UserRepository, "update", update)
    monkeypatch.setattr(
        UserRepository, "get_active_admins_for_update",
        lambda self: [u for u in users.values() if u.role == "admin" and u.is_active],
    )
    app.dependency_overrides[get_db] = fake_get_db
    yield TestClient(app), users, db
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def register(client, email="student@example.com", password="password123", **extra):
    return client.post("/api/v1/auth/register", json={
        "email": email, "password": password, "full_name": "Student", **extra,
    })


def token(client, email="student@example.com", password="password123"):
    response = client.post("/api/v1/auth/login", json={
        "email": email, "password": password,
    })
    assert response.status_code == 200
    return response.json()["access_token"]


def bearer(value):
    return {"Authorization": f"Bearer {value}"}


def add_user(users, email, role):
    user = SimpleNamespace(
        id=uuid4(), email=email, password_hash=hash_password("secret6"),
        full_name="User", role=role, is_active=True,
    )
    users[email] = user
    return user


def test_registration_validation_and_hash(client):
    api, users, db = client
    response = register(api, "  STudent@EXAMPLE.com  ", "123456")
    assert response.status_code == 201
    assert response.json()["email"] == "student@example.com"
    assert response.json()["role"] == "student"
    assert response.json()["is_active"] is True
    assert "password_hash" not in response.json()
    assert users["student@example.com"].password_hash != "123456"
    assert verify_password("123456", users["student@example.com"].password_hash)
    assert db.commit.called
    assert register(api, "student@example.com").status_code == 409
    assert register(api, "invalid-email").status_code == 422
    assert register(api, "x@example.com", "12345").status_code == 422
    assert register(api, "x@example.com", role="admin").status_code == 422
    assert register(api, "x@example.com", role="teacher").status_code == 422


def test_hashes_are_salted():
    first, second = hash_password("password"), hash_password("password")
    assert first != second
    assert verify_password("password", first)
    assert not verify_password("wrong", first)


def test_login_and_me(client):
    api, users, _ = client
    register(api)
    assert api.post("/api/v1/auth/login", json={
        "email": "unknown@example.com", "password": "password123",
    }).status_code == 401
    assert api.post("/api/v1/auth/login", json={
        "email": "student@example.com", "password": "wrong",
    }).status_code == 401
    access = token(api, "  STUDENT@example.com ")
    response = api.get("/api/v1/auth/me", headers=bearer(access))
    assert response.status_code == 200
    assert response.json()["id"] == str(users["student@example.com"].id)
    assert "password_hash" not in response.json()
    assert api.get("/api/v1/auth/me").status_code == 401
    assert api.get("/api/v1/auth/me", headers=bearer("bad")).status_code == 401
    users["student@example.com"].is_active = False
    assert api.get("/api/v1/auth/me", headers=bearer(access)).status_code == 403
    assert api.post("/api/v1/auth/login", json={
        "email": "student@example.com", "password": "password123",
    }).status_code == 403


def test_jwt_rejection(client):
    api, users, _ = client
    user = add_user(users, "student@example.com", "student")
    access, expires = create_access_token(user.id)
    assert expires == 1800
    assert decode_access_token(access) == user.id
    now = datetime.now(timezone.utc)
    cases = [
        "malformed",
        jwt.encode({"sub": str(user.id), "type": "access", "iat": now,
                    "exp": now + timedelta(minutes=30)}, "another-test-key-at-least-thirty-two-bytes", algorithm="HS256"),
        jwt.encode({"sub": str(user.id), "type": "access", "iat": now - timedelta(hours=1),
                    "exp": now - timedelta(minutes=1)}, SECRET, algorithm="HS256"),
        jwt.encode({"sub": str(user.id), "type": "refresh", "iat": now,
                    "exp": now + timedelta(minutes=30)}, SECRET, algorithm="HS256"),
        jwt.encode({"type": "access", "iat": now,
                    "exp": now + timedelta(minutes=30)}, SECRET, algorithm="HS256"),
        jwt.encode({"sub": "invalid", "type": "access", "iat": now,
                    "exp": now + timedelta(minutes=30)}, SECRET, algorithm="HS256"),
    ]
    for value in cases:
        assert api.get("/api/v1/auth/me", headers=bearer(value)).status_code == 401
    users.clear()
    assert api.get("/api/v1/auth/me", headers=bearer(access)).status_code == 401


def test_admin_endpoints_and_rbac(client):
    api, users, _ = client
    admin = add_user(users, "admin@example.com", "admin")
    teacher = add_user(users, "teacher@example.com", "teacher")
    student = add_user(users, "student@example.com", "student")
    admin_token = token(api, admin.email, "secret6")
    for user in (teacher, student):
        assert api.get("/api/v1/users", headers=bearer(token(api, user.email, "secret6"))).status_code == 403
    assert api.get("/api/v1/users").status_code == 401
    for role in ("teacher", "student", "admin"):
        response = api.post("/api/v1/users", headers=bearer(admin_token), json={
            "email": f"new-{role}@example.com", "password": "123456",
            "full_name": "New User", "role": role,
        })
        assert response.status_code == 201
        assert response.json()["role"] == role
        assert "password_hash" not in response.json()
    assert api.post("/api/v1/users", headers=bearer(admin_token), json={
        "email": "new-teacher@example.com", "password": "123456",
        "full_name": "New User", "role": "teacher",
    }).status_code == 409
    assert api.get("/api/v1/users?limit=0", headers=bearer(admin_token)).status_code == 422
    assert api.get("/api/v1/users?offset=-1", headers=bearer(admin_token)).status_code == 422
    assert api.get("/api/v1/users?limit=2", headers=bearer(admin_token)).status_code == 200
    assert api.get(f"/api/v1/users/{uuid4()}", headers=bearer(admin_token)).status_code == 404
    assert api.patch(f"/api/v1/users/{student.id}/status", headers=bearer(admin_token),
                     json={"is_active": False}).status_code == 200
    assert not student.is_active
    assert api.patch(f"/api/v1/users/{student.id}/status", headers=bearer(admin_token),
                     json={"is_active": True}).status_code == 200
    assert api.patch(f"/api/v1/users/{admin.id}/status", headers=bearer(admin_token),
                     json={"is_active": False}).status_code == 409
    admin.role = "teacher"
    assert api.get("/api/v1/users", headers=bearer(admin_token)).status_code == 403


def test_final_active_admin_cannot_be_deactivated(client):
    _, users, db = client
    actor = add_user(users, "actor@example.com", "admin")
    target = add_user(users, "target@example.com", "admin")
    actor.is_active = False
    with pytest.raises(UserStatusError, match="cuối cùng"):
        UserService(db).update_status(target.id, False, actor)
    assert target.is_active


def test_seed_admin(monkeypatch, client):
    _, users, db = client
    monkeypatch.setenv("SEED_ADMIN_EMAIL", "  SEED@EXAMPLE.COM  ")
    monkeypatch.setenv("SEED_ADMIN_FULL_NAME", "Seed Admin")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "secret6")

    class Context:
        def __enter__(self):
            return db

        def __exit__(self, *_):
            pass

    monkeypatch.setattr(seed_admin, "get_session_factory", lambda: lambda: Context())
    assert seed_admin.seed_admin() is True
    original_hash = users["seed@example.com"].password_hash
    assert users["seed@example.com"].role == "admin"
    assert seed_admin.seed_admin() is False
    assert users["seed@example.com"].password_hash == original_hash
    users["seed@example.com"].role = "student"
    with pytest.raises(ValueError, match="non-Admin"):
        seed_admin.seed_admin()
    monkeypatch.delenv("SEED_ADMIN_PASSWORD")
    with pytest.raises(ValueError, match="SEED_ADMIN_PASSWORD"):
        seed_admin.seed_admin()


def test_openapi_security(client):
    api, _, _ = client
    schema = api.get("/openapi.json").json()
    assert "HTTPBearer" in schema["components"]["securitySchemes"]
    for path in ("/api/v1/auth/register", "/api/v1/auth/login", "/api/v1/auth/me",
                 "/api/v1/users", "/api/v1/users/{user_id}",
                 "/api/v1/users/{user_id}/status"):
        assert path in schema["paths"]


def test_missing_or_weak_jwt_secret(monkeypatch):
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        create_access_token(uuid4())
    monkeypatch.setenv("JWT_SECRET_KEY", "weak")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        create_access_token(uuid4())
    get_settings.cache_clear()
