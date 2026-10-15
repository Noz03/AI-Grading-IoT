import json
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ai_grading_iot.api.dependencies import get_rubric_generator
from ai_grading_iot.core.config import get_settings
from ai_grading_iot.core.security import create_access_token
from ai_grading_iot.db.session import get_db, get_engine
from ai_grading_iot.graders.rubric_generator import RubricGenerator
from ai_grading_iot.main import app
from ai_grading_iot.repositories.practice_repository import PracticeRepository
from ai_grading_iot.repositories.rubric_repository import RubricRepository
from ai_grading_iot.repositories.user_repository import UserRepository


class StubClient:
    def __init__(self):
        self.fail = False
        self.calls = 0
        self.on_generate = None

    def generate(self, prompt):
        self.calls += 1
        if self.on_generate:
            self.on_generate()
        if self.fail:
            raise RuntimeError("provider secret must not leak")
        return json.dumps({"rubrics": [
            {"type": "code", "weight": 70, "criteria": ["Initialize LED GPIO"]},
            {"type": "data", "weight": 0, "criteria": []},
            {"type": "vision", "weight": 30, "criteria": ["Wire LED to board"]},
        ]})


@pytest.fixture
def context(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "module-three-integration-secret-at-least-32-bytes")
    get_settings.cache_clear()
    stub = StubClient()
    with get_engine().connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint",
                     autoflush=False, expire_on_commit=False) as db:
            app.dependency_overrides[get_db] = lambda: db
            app.dependency_overrides[get_rubric_generator] = lambda: RubricGenerator(stub)
            users = UserRepository(db)
            actors = {}
            for role in ("admin", "teacher", "teacher", "student", "student"):
                user = users.create(email=f"{uuid4().hex}@example.com", password_hash="test",
                                    full_name=role, role=role)
                actors.setdefault(role, []).append(user)
            db.commit()
            def headers(role, index=0):
                return {"Authorization": f"Bearer {create_access_token(actors[role][index].id)[0]}"}
            try:
                yield TestClient(app), db, stub, actors, headers
            finally:
                app.dependency_overrides.clear()
                db.close()
                transaction.rollback()
    get_settings.cache_clear()


def practice_data():
    return {"title": "LED", "description": "Control LED",
            "requirements": {"objective": "Control LED", "tasks": [{"order": 1, "description": "Wire LED"}]},
            "environment": {"board": "ESP32", "framework": "Arduino", "language": "C++"},
            "rubric": {}, "metadata": {"created_by": "untrusted"}}


def setup_course(context):
    client, db, stub, actors, headers = context
    code = f"IOT_{uuid4().hex[:12]}"
    cid = client.post("/api/v1/courses", json={"code": code, "name": "IoT"},
                      headers=headers("admin")).json()["id"]
    client.post(f"/api/v1/courses/{cid}/teachers", json={"teacher_id": str(actors["teacher"][0].id)},
                headers=headers("admin"))
    client.post("/api/v1/courses/join", json={"course_code": code}, headers=headers("student"))
    return cid


def test_creation_access_edit_publish_and_regeneration(context):
    client, db, stub, actors, headers = context
    cid = setup_course(context)
    endpoint = f"/api/v1/courses/{cid}/practices"
    assert client.post(endpoint, json=practice_data(), headers=headers("student")).status_code == 403
    assert stub.calls == 0
    created = client.post(endpoint, json=practice_data(), headers=headers("teacher"))
    assert created.status_code == 201, created.text
    assert created.json()["rubric_generation"]["status"] == "succeeded"
    pid = created.json()["practice_id"]
    model = PracticeRepository(db).get_by_id(UUID(pid))
    assert model.status == "draft"
    rubrics = client.get(f"/api/v1/practices/{pid}/rubrics", headers=headers("teacher")).json()
    assert len(rubrics) == 3
    assert model.rubric_reference["dashboard_rubric_id"] == next(
        item["id"] for item in rubrics if item["type"] == "data")
    rid = next(item["id"] for item in rubrics if item["type"] == "code")
    assert client.get(f"/api/v1/rubrics/{rid}", headers=headers("teacher", 1)).status_code == 403
    assert client.get(f"/api/v1/practices/{pid}/rubrics", headers=headers("student")).status_code == 403
    assert client.patch(f"/api/v1/rubrics/{rid}", json={"id": str(uuid4())},
                        headers=headers("teacher")).status_code == 422
    edited = client.patch(f"/api/v1/rubrics/{rid}", json={"criteria": ["Reviewed criterion"]},
                          headers=headers("teacher"))
    assert edited.status_code == 200, edited.text
    assert client.post(f"/api/v1/practices/{pid}/rubrics/generate",
                       headers=headers("teacher")).status_code == 409
    assert client.get(f"/api/v1/rubrics/{rid}", headers=headers("teacher")).json()["criteria"] == ["Reviewed criterion"]
    def concurrent_edit():
        RubricRepository(db).get_by_id(UUID(rid)).criteria = ["Concurrent teacher edit"]
        db.commit()
        stub.on_generate = None
    stub.on_generate = concurrent_edit
    assert client.post(f"/api/v1/practices/{pid}/rubrics/regenerate",
                       headers=headers("teacher")).status_code == 409
    assert client.get(f"/api/v1/rubrics/{rid}", headers=headers("teacher")).json()["criteria"] == ["Concurrent teacher edit"]
    stub.fail = True
    assert client.post(f"/api/v1/practices/{pid}/rubrics/regenerate",
                       headers=headers("teacher")).status_code == 503
    assert client.get(f"/api/v1/rubrics/{rid}", headers=headers("teacher")).json()["criteria"] == ["Concurrent teacher edit"]
    stub.fail = False
    regenerated = client.post(f"/api/v1/practices/{pid}/rubrics/regenerate",
                              headers=headers("teacher"))
    assert regenerated.status_code == 200, regenerated.text
    assert next(item for item in regenerated.json() if item["type"] == "code")["id"] == rid
    assert client.post(f"/api/v1/practices/{pid}/publish", headers=headers("teacher")).status_code == 200
    assert client.get(f"/api/v1/rubrics/{rid}", headers=headers("student")).status_code == 200
    assert client.get(f"/api/v1/rubrics/{rid}", headers=headers("student", 1)).status_code == 403
    assert client.patch(f"/api/v1/rubrics/{rid}", json={"weight": 50},
                        headers=headers("admin")).status_code == 409
    assert client.post(f"/api/v1/practices/{pid}/rubrics/regenerate",
                       headers=headers("teacher")).status_code == 409


def test_failure_retry_and_publication_validation(context):
    client, db, stub, actors, headers = context
    cid = setup_course(context)
    stub.fail = True
    created = client.post(f"/api/v1/courses/{cid}/practices", json=practice_data(),
                          headers=headers("admin"))
    assert created.status_code == 201
    assert created.json()["rubric_generation"]["status"] == "failed"
    assert "secret" not in created.text
    pid = created.json()["practice_id"]
    assert PracticeRepository(db).get_by_id(UUID(pid)) is not None
    assert RubricRepository(db).get_by_practice(UUID(pid)) == []
    assert client.post(f"/api/v1/practices/{pid}/publish", headers=headers("admin")).status_code == 409
    stub.fail = False
    retry = client.post(f"/api/v1/practices/{pid}/rubrics/generate", headers=headers("admin"))
    assert retry.status_code == 200, retry.text
    code = next(item for item in retry.json() if item["type"] == "code")
    assert client.patch(f"/api/v1/rubrics/{code['id']}", json={"weight": 60},
                        headers=headers("admin")).status_code == 200
    assert client.post(f"/api/v1/practices/{pid}/publish", headers=headers("admin")).status_code == 409
    assert client.patch(f"/api/v1/rubrics/{code['id']}", json={"weight": 70},
                        headers=headers("admin")).status_code == 200
    assert client.post(f"/api/v1/practices/{pid}/publish", headers=headers("admin")).status_code == 200


def test_stale_practice_and_atomic_persistence(context, monkeypatch):
    client, db, stub, actors, headers = context
    cid = setup_course(context)
    stub.fail = True
    pid = client.post(f"/api/v1/courses/{cid}/practices", json=practice_data(),
                      headers=headers("admin")).json()["practice_id"]
    stub.fail = False
    def change_practice():
        model = PracticeRepository(db).get_by_id(UUID(pid))
        model.description = "Changed while Groq was running"
        db.commit()
        stub.on_generate = None
    stub.on_generate = change_practice
    assert client.post(f"/api/v1/practices/{pid}/rubrics/generate",
                       headers=headers("admin")).status_code == 409
    assert RubricRepository(db).get_by_practice(UUID(pid)) == []

    original_create = RubricRepository.create
    calls = 0
    def fail_second(self, *, practice_id, rubric):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated write failure")
        return original_create(self, practice_id=practice_id, rubric=rubric)
    monkeypatch.setattr(RubricRepository, "create", fail_second)
    result = client.post(f"/api/v1/practices/{pid}/rubrics/generate", headers=headers("admin"))
    assert result.status_code == 503
    assert "simulated" not in result.text
    assert RubricRepository(db).get_by_practice(UUID(pid)) == []
    assert PracticeRepository(db).get_by_id(UUID(pid)).rubric_reference == {
        "code_rubric_id": None, "dashboard_rubric_id": None, "vision_rubric_id": None}


def test_openapi_module3_routes():
    paths = app.openapi()["paths"]
    for path, method in {
        "/api/v1/practices/{practice_id}/rubrics/generate": "post",
        "/api/v1/practices/{practice_id}/rubrics/regenerate": "post",
        "/api/v1/practices/{practice_id}/rubrics": "get",
        "/api/v1/rubrics/{rubric_id}": "patch",
    }.items():
        assert method in paths[path]
