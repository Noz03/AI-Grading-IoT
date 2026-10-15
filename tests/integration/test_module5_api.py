import json
import io
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from ai_grading_iot.clients.groq_client import GroqClient
from ai_grading_iot.core.config import get_settings
from ai_grading_iot.core.security import create_access_token
from ai_grading_iot.db.session import get_db, get_engine
from ai_grading_iot.main import app
from ai_grading_iot.models.practice import Practice
from ai_grading_iot.models.rubric import Rubric
from ai_grading_iot.repositories.course_repository import CourseRepository
from ai_grading_iot.repositories.grading_repository import GradingRepository
from ai_grading_iot.repositories.submission_repository import SubmissionRepository
from ai_grading_iot.repositories.user_repository import UserRepository


@pytest.fixture
def grading_context(monkeypatch, tmp_path):
    monkeypatch.setenv("JWT_SECRET_KEY", "module-five-test-secret-at-least-32-bytes")
    monkeypatch.setenv("GROQ_API_KEY", "mocked-key")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    get_settings.cache_clear()
    with get_engine().connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint", autoflush=False, expire_on_commit=False) as db:
            app.dependency_overrides[get_db] = lambda: db
            users = UserRepository(db)
            actors = {}
            for role in ("admin", "teacher", "teacher", "student", "student"):
                actors.setdefault(role, []).append(users.create(email=f"{uuid4().hex}@example.com",
                                                                 password_hash="test", full_name=role, role=role))
            courses = CourseRepository(db)
            course = courses.create(code=uuid4().hex, name="IoT")
            courses.assign_teacher(course_id=course.id, teacher_id=actors["teacher"][0].id)
            courses.enroll_student(course_id=course.id, student_id=actors["student"][0].id)
            rubric_ids = {kind: uuid4() for kind in ("code", "data", "vision")}
            practice = Practice(id=uuid4(), course_id=course.id, title="IoT", description="Sensors",
                                requirements={"objective": "Process temperature", "tasks": [{"id": str(uuid4()), "order": 1,
                                "description": "Process readings"}], "constraints": []},
                                environment={"board": "ESP32", "framework": "Arduino", "language": "C++", "libraries": []},
                                hardware=[], status="published", version="1.0",
                                rubric_reference={"code_rubric_id": str(rubric_ids["code"]),
                                                  "dashboard_rubric_id": str(rubric_ids["data"]),
                                                  "vision_rubric_id": str(rubric_ids["vision"])},
                                practice_metadata={"created_by": "test", "created_at": "2026-01-01T00:00:00Z",
                                                   "updated_at": "2026-01-01T00:00:00Z"})
            db.add(practice)
            for kind, weight, criteria in (("code", 60, ["Process readings"]),
                                           ("data", 40, ["Calculate temperature"]), ("vision", 0, [])):
                db.add(Rubric(id=rubric_ids[kind], practice_id=practice.id, type=kind,
                              weight=weight, criteria=criteria))
            db.commit()

            def headers(role, index=0):
                return {"Authorization": f"Bearer {create_access_token(actors[role][index].id)[0]}"}

            calls = []
            def generate(self, prompt):
                assert not db.in_transaction(), "Groq request held a database transaction"
                calls.append(prompt)
                if "CODE RUBRIC CRITERIA" in prompt:
                    return json.dumps({"criteria_results": [{"criterion": "Process readings", "score": 90,
                                                             "feedback": "Present"}], "code_score": 90,
                                       "overall_feedback": "Static code review"})
                return json.dumps({"score": 80, "feedback": "Measurements align", "criteria_feedback": [],
                                   "evidence_status": "sufficient"})
            monkeypatch.setattr(GroqClient, "generate", generate)
            try:
                yield TestClient(app), db, actors, headers, practice, calls
            finally:
                app.dependency_overrides.clear()
                db.close()
                transaction.rollback()
    get_settings.cache_clear()


def make_submission(context, *, submit=True):
    client, _, _, headers, practice, _ = context
    response = client.post(f"/api/v1/practices/{practice.id}/submissions", json={"code": "float t = 25;"},
                           headers=headers("student"))
    assert response.status_code == 201, response.text
    sid = response.json()["id"]
    if submit:
        response = client.post(f"/api/v1/submissions/{sid}/submit", headers=headers("student"))
        assert response.status_code == 200
    return sid


def test_grading_api_and_authorization(grading_context):
    client, db, actors, headers, _, calls = grading_context
    sid = make_submission(grading_context, submit=False)
    endpoint = f"/api/v1/submissions/{sid}/grade"
    assert client.post(endpoint).status_code == 401
    assert client.post(endpoint, headers=headers("student", 1)).status_code == 403
    assert client.post(endpoint, headers=headers("teacher", 1)).status_code == 403
    assert client.post(endpoint, headers=headers("student")).status_code == 409
    assert calls == []
    client.post(f"/api/v1/submissions/{sid}/submit", headers=headers("student"))
    assert calls == []
    response = client.post(endpoint, headers=headers("student"))
    assert response.status_code == 201, response.text
    result = response.json()
    assert (result["code_score"], result["data_score"], result["vision_score"], result["final_score"]) == (90, 80, None, 86)
    assert result["status"] == "complete"
    assert result["code_evaluation"] and result["data_evaluation"]
    assert client.post(endpoint, headers=headers("admin")).status_code == 409
    assert client.get(f"/api/v1/submissions/{sid}/grading-result", headers=headers("teacher")).json()["id"] == result["id"]
    assert client.get(f"/api/v1/grading-results/{result['id']}", headers=headers("student", 1)).status_code == 403
    assert client.post(f"/api/v1/submissions/{sid}/regrade", headers=headers("student")).status_code == 403
    assert client.post(f"/api/v1/submissions/{sid}/regrade", headers=headers("teacher", 1)).status_code == 403
    assert len(calls) == 2


def test_revision_evidence_and_invalidation(grading_context):
    client, db, _, headers, _, calls = grading_context
    sid = make_submission(grading_context)
    path = f"/api/v1/submissions/{sid}"
    assert client.patch(path, content='{"data_evidence":{"measurements":[{"name":"temperature","value":NaN}]}}',
                        headers={**headers("student"), "Content-Type": "application/json"}).status_code == 422
    assert client.patch(path, json={"data_evidence": {"measurements": [{"name": "temperature", "value": "25"}]}},
                        headers=headers("student")).status_code == 422
    assert client.patch(path, json={"data_evidence": {"dashboard": {"image_ids": [str(uuid4())]}}},
                        headers=headers("student")).status_code == 404
    assert client.get(path, headers=headers("student")).json()["revision"] == 1
    payload = {"measurements": [{"name": "temperature", "value": 25, "unit": "C"}]}
    changed = client.patch(path, json={"data_evidence": payload}, headers=headers("student"))
    assert changed.status_code == 200 and changed.json()["revision"] == 2
    assert changed.json()["status"] == "draft"
    same = client.patch(path, json={"data_evidence": payload}, headers=headers("student"))
    assert same.json()["revision"] == 2
    assert client.post(f"{path}/submit", headers=headers("student")).json()["revision"] == 2
    assert calls == []
    grade = client.post(f"{path}/grade", headers=headers("student"))
    assert grade.status_code == 201, grade.text
    cleared = client.patch(path, json={"data_evidence": None}, headers=headers("student"))
    assert cleared.json()["revision"] == 3
    assert cleared.json()["data_evidence"] is None
    assert GradingRepository(db).get_by_submission(UUID(sid)) is None


def test_regrade_failure_and_stale_results(grading_context, monkeypatch):
    client, db, _, headers, practice, calls = grading_context
    sid = make_submission(grading_context)
    endpoint = f"/api/v1/submissions/{sid}"
    original = client.post(f"{endpoint}/grade", headers=headers("admin")).json()
    def failure(self, prompt):
        raise RuntimeError("provider secret")
    monkeypatch.setattr(GroqClient, "generate", failure)
    failed = client.post(f"{endpoint}/regrade", headers=headers("teacher"))
    assert failed.status_code == 502 and "secret" not in failed.text
    assert client.get(f"{endpoint}/grading-result", headers=headers("admin")).json() == original

    def mutate(self, prompt):
        assert not db.in_transaction()
        if "CODE RUBRIC CRITERIA" in prompt:
            model = SubmissionRepository(db).get_by_id(UUID(sid))
            model.code = "changed during grading"
            model.revision += 1
            model.status = "draft"
            db.commit()
            return json.dumps({"criteria_results": [{"criterion": "Process readings", "score": 90,
                                                    "feedback": "Present"}], "code_score": 90, "overall_feedback": "Review"})
        return json.dumps({"score": 80, "feedback": "Measurements align", "criteria_feedback": [],
                           "evidence_status": "sufficient"})
    monkeypatch.setattr(GroqClient, "generate", mutate)
    assert client.post(f"{endpoint}/regrade", headers=headers("teacher")).status_code == 409
    # A provider callback that edits the submission cannot replace the saved result.
    assert GradingRepository(db).get_by_submission(UUID(sid)).id == UUID(original["id"])


def test_migration_columns_and_openapi():
    inspector = inspect(get_engine())
    assert {"data_evidence", "revision"}.issubset({item["name"] for item in inspector.get_columns("submissions")})
    assert "data_evaluation" in {item["name"] for item in inspector.get_columns("grading_results")}
    paths = app.openapi()["paths"]
    for path in ("/api/v1/submissions/{submission_id}/grade",
                 "/api/v1/submissions/{submission_id}/regrade",
                 "/api/v1/submissions/{submission_id}/grading-result",
                 "/api/v1/grading-results/{result_id}"):
        assert path in paths


def test_partial_scores_and_successful_regrade(grading_context, monkeypatch):
    client, db, _, headers, practice, calls = grading_context
    sid = make_submission(grading_context)
    for rubric in practice.rubrics:
        if rubric.type == "code":
            rubric.weight = 50
        elif rubric.type == "data":
            rubric.weight = 30
        else:
            rubric.weight = 20
            rubric.criteria = ["Physical wiring"]
    db.commit()
    path = f"/api/v1/submissions/{sid}"
    original = client.post(f"{path}/grade", headers=headers("admin"))
    assert original.status_code == 201, original.text
    assert original.json()["vision_score"] is None and original.json()["final_score"] is None
    assert original.json()["status"] == "partial"
    identifier = original.json()["id"]
    retry = client.post(f"{path}/regrade", headers=headers("teacher"))
    assert retry.status_code == 200, retry.text
    assert retry.json()["id"] == identifier

    previous = GroqClient.generate
    def insufficient(self, prompt):
        if "CODE RUBRIC CRITERIA" in prompt:
            return previous(self, prompt)
        return json.dumps({"score": None, "feedback": "Readings are unavailable", "criteria_feedback": [],
                           "evidence_status": "insufficient"})
    monkeypatch.setattr(GroqClient, "generate", insufficient)
    updated = client.post(f"{path}/regrade", headers=headers("admin"))
    assert updated.status_code == 200, updated.text
    assert updated.json()["id"] == identifier
    assert updated.json()["data_score"] is None and updated.json()["final_score"] is None
    assert updated.json()["status"] == "insufficient_evidence"


def test_stale_rubric_change_rejected(grading_context, monkeypatch):
    client, db, _, headers, practice, _ = grading_context
    sid = make_submission(grading_context)
    original_generate = GroqClient.generate
    def change_rubric(self, prompt):
        if "CODE RUBRIC CRITERIA" in prompt:
            next(row for row in practice.rubrics if row.type == "data").criteria = ["Changed criterion"]
            db.commit()
        return original_generate(self, prompt)
    monkeypatch.setattr(GroqClient, "generate", change_rubric)
    response = client.post(f"/api/v1/submissions/{sid}/grade", headers=headers("teacher"))
    assert response.status_code == 409, response.text
    assert GradingRepository(db).get_by_submission(UUID(sid)) is None


def test_image_revision_and_dashboard_references(grading_context):
    client, db, _, headers, _, _ = grading_context
    sid = make_submission(grading_context)
    path = f"/api/v1/submissions/{sid}"
    payload = io.BytesIO()
    Image.new("RGB", (32, 32), "blue").save(payload, format="PNG")
    uploaded = client.post(f"{path}/images", files={"file": ("dashboard.png", payload.getvalue(), "image/png")},
                           headers=headers("student"))
    assert uploaded.status_code == 201, uploaded.text
    image_id = uploaded.json()["image_id"]
    assert client.get(path, headers=headers("student")).json()["revision"] == 2
    evidence = {"dashboard": {"description": "Sensor dashboard", "image_ids": [image_id]}}
    patched = client.patch(path, json={"data_evidence": evidence}, headers=headers("student"))
    assert patched.status_code == 200 and patched.json()["revision"] == 3
    deleted = client.delete(f"{path}/images/{image_id}", headers=headers("student"))
    assert deleted.status_code == 204
    current = client.get(path, headers=headers("student")).json()
    assert current["revision"] == 4
    assert current["data_evidence"]["dashboard"]["image_ids"] == []
    assert client.patch(path, json={"data_evidence": evidence}, headers=headers("student")).status_code == 404


def test_zero_weight_skips_data_and_failed_write_rolls_back(grading_context, monkeypatch):
    client, db, _, headers, practice, calls = grading_context
    sid = make_submission(grading_context)
    next(row for row in practice.rubrics if row.type == "code").weight = 100
    next(row for row in practice.rubrics if row.type == "data").weight = 0
    db.commit()
    original_create = GradingRepository.create
    def broken_create(self, **kwargs):
        original_create(self, **kwargs)
        raise RuntimeError("database write failed")
    monkeypatch.setattr(GradingRepository, "create", broken_create)
    path = f"/api/v1/submissions/{sid}/grade"
    assert client.post(path, headers=headers("admin")).status_code == 502
    assert GradingRepository(db).get_by_submission(UUID(sid)) is None
    monkeypatch.setattr(GradingRepository, "create", original_create)
    result = client.post(path, headers=headers("admin"))
    assert result.status_code == 201, result.text
    assert result.json()["code_score"] == 90 and result.json()["data_score"] is None
    assert result.json()["final_score"] == 90
    assert len(calls) == 2 and all("CODE RUBRIC CRITERIA" in item for item in calls)
