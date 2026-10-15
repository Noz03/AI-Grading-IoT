from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ai_grading_iot.core.config import get_settings
from ai_grading_iot.core.security import create_access_token
from ai_grading_iot.db.session import get_db, get_engine
from ai_grading_iot.main import app
from ai_grading_iot.api.dependencies import get_rubric_generator
from ai_grading_iot.graders.rubric_generator import RubricGenerator
from ai_grading_iot.repositories.user_repository import UserRepository
from ai_grading_iot.repositories.course_repository import CourseRepository
from ai_grading_iot.repositories.practice_repository import PracticeRepository
from ai_grading_iot.repositories.rubric_repository import RubricRepository
from ai_grading_iot.repositories.submission_repository import SubmissionRepository
from ai_grading_iot.repositories.grading_repository import GradingRepository
from ai_grading_iot.schemas.rubric import Rubric, RubricType
from ai_grading_iot.schemas.submission import Submission as SubmissionSchema, SubmissionStatus


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "module-two-integration-secret-at-least-32-bytes")
    get_settings.cache_clear()
    with get_engine().connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint",
                     autoflush=False, expire_on_commit=False) as db:
            app.dependency_overrides[get_db] = lambda: db
            # Module 2 tests exercise manual rubric setup and failure recovery.
            # Keep the new automatic generation deterministic without provider calls.
            class UnavailableClient:
                def generate(self, prompt):
                    raise RuntimeError("provider unavailable")

            app.dependency_overrides[get_rubric_generator] = lambda: RubricGenerator(UnavailableClient())
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
                yield TestClient(app), db, actors, headers
            finally:
                app.dependency_overrides.clear()
                db.close()
                transaction.rollback()
    get_settings.cache_clear()


def practice_data():
    return {
        "title": "LED", "description": "Control LED",
        "requirements": {"objective": "Control LED", "tasks": [{"order": 1, "description": "Wire LED"}]},
        "environment": {"board": "ESP32", "framework": "Arduino", "language": "C++"},
        "rubric": {}, "metadata": {"created_by": "untrusted"},
    }


def test_courses_and_memberships(setup):
    client, db, actors, headers = setup
    code = f"IOT_{uuid4().hex[:12]}"
    assert client.post("/api/v1/courses", json={"code": code, "name": "IoT"},
                       headers=headers("teacher")).status_code == 403
    created = client.post("/api/v1/courses", json={"code": code, "name": "IoT"},
                          headers=headers("admin"))
    assert created.status_code == 201
    cid = created.json()["id"]
    assert client.post("/api/v1/courses", json={"code": code, "name": "duplicate"},
                       headers=headers("admin")).status_code == 409
    assert client.get(f"/api/v1/courses/{cid}", headers=headers("student")).status_code == 403
    assert client.post(f"/api/v1/courses/{cid}/teachers", json={"teacher_id": str(actors['student'][0].id)},
                      headers=headers("admin")).status_code == 422
    teacher_id = actors["teacher"][0].id
    assert client.post(f"/api/v1/courses/{cid}/teachers", json={"teacher_id": str(teacher_id)},
                      headers=headers("admin")).status_code == 201
    assert client.post(f"/api/v1/courses/{cid}/teachers", json={"teacher_id": str(teacher_id)},
                      headers=headers("admin")).status_code == 409
    assert client.get(f"/api/v1/courses/{cid}", headers=headers("teacher")).status_code == 200
    assert client.get(f"/api/v1/courses/{cid}", headers=headers("teacher", 1)).status_code == 403
    assert client.post("/api/v1/courses/join", json={"course_code": code},
                       headers=headers("teacher")).status_code == 403
    assert client.post("/api/v1/courses/join", json={"course_code": code},
                       headers=headers("student")).status_code == 201
    assert client.post("/api/v1/courses/join", json={"course_code": code},
                       headers=headers("student")).status_code == 409
    assert client.get(f"/api/v1/courses/{cid}", headers=headers("student")).status_code == 200
    assert client.delete(f"/api/v1/courses/{cid}/students/{actors['student'][0].id}",
                         headers=headers("teacher")).status_code == 403
    assert client.delete(f"/api/v1/courses/{cid}/students/{actors['student'][0].id}",
                         headers=headers("admin")).status_code == 204
    assert client.get(f"/api/v1/courses/{cid}", headers=headers("student")).status_code == 403
    assert client.patch(f"/api/v1/courses/{cid}", json={"name": "New IoT", "description": None},
                        headers=headers("admin")).json()["name"] == "New IoT"
    assert client.delete(f"/api/v1/courses/{cid}", headers=headers("admin")).status_code == 204
    assert CourseRepository(db).get_by_id(UUID(cid)) is None


def test_practice_authorization_status_and_history(setup):
    client, db, actors, headers = setup
    code = f"IOT_{uuid4().hex[:12]}"
    cid = client.post("/api/v1/courses", json={"code": code, "name": "IoT"},
                      headers=headers("admin")).json()["id"]
    client.post(f"/api/v1/courses/{cid}/teachers", json={"teacher_id": str(actors['teacher'][0].id)}, headers=headers("admin"))
    client.post("/api/v1/courses/join", json={"course_code": code}, headers=headers("student"))
    endpoint = f"/api/v1/courses/{cid}/practices"
    assert client.post(endpoint, json=practice_data(), headers=headers("student")).status_code == 403
    assert client.post(endpoint, json=practice_data(), headers=headers("teacher", 1)).status_code == 403
    response = client.post(endpoint, json=practice_data(), headers=headers("teacher"))
    assert response.status_code == 201, response.text
    pid = response.json()["practice_id"]
    assert response.json()["metadata"]["created_by"] == str(actors["teacher"][0].id)
    assert client.get(endpoint, headers=headers("student")).json() == []
    assert client.get(f"/api/v1/practices/{pid}", headers=headers("student")).status_code == 403
    assert client.post(f"/api/v1/practices/{pid}/publish",
                       headers=headers("teacher")).status_code == 409
    assert PracticeRepository(db).get_by_id(uuid4()) is None
    model = PracticeRepository(db).get_by_id(UUID(pid))
    rubrics = [Rubric(type=kind, weight=weight, criteria=["Valid criterion"])
               for kind, weight in [(RubricType.CODE, 50), (RubricType.DATA, 30),
                                    (RubricType.VISION, 20)]]
    for rubric in rubrics:
        RubricRepository(db).create(practice_id=model.id, rubric=rubric)
    model.rubric_reference = {
        "code_rubric_id": str(rubrics[0].id),
        "dashboard_rubric_id": str(rubrics[1].id),
        "vision_rubric_id": str(rubrics[2].id),
    }
    db.commit()
    assert client.post(f"/api/v1/practices/{pid}/publish",
                       headers=headers("teacher", 1)).status_code == 403
    assert client.post(f"/api/v1/practices/{pid}/publish",
                       headers=headers("teacher")).status_code == 200
    assert len(client.get(endpoint, headers=headers("student")).json()) == 1
    submission = SubmissionRepository(db).create(submission=SubmissionSchema(
        practice_id=model.id, student_id=actors["student"][0].id,
        description="work", code="void setup() {}", status=SubmissionStatus.SUBMITTED))
    grading = GradingRepository(db).create(submission_id=submission.id, code_score=90)
    db.commit()
    assert client.patch(f"/api/v1/practices/{pid}", json={"title": "Changed"},
                        headers=headers("teacher")).status_code == 409
    assert client.delete(f"/api/v1/practices/{pid}", headers=headers("admin")).status_code == 409
    assert client.delete(f"/api/v1/courses/{cid}", headers=headers("admin")).status_code == 409
    assert client.post(f"/api/v1/practices/{pid}/archive",
                       headers=headers("teacher")).status_code == 200
    assert client.get(endpoint, headers=headers("student")).json() == []
    assert client.get(f"/api/v1/practices/{pid}", headers=headers("student")).status_code == 403
    assert client.delete(f"/api/v1/courses/{cid}/students/{actors['student'][0].id}",
                         headers=headers("admin")).status_code == 204
    assert client.get(f"/api/v1/courses/{cid}", headers=headers("student")).status_code == 403
    assert SubmissionRepository(db).get_by_id(submission.id) is not None
    assert GradingRepository(db).get_by_id(grading.id) is not None
    assert client.post("/api/v1/courses/join", json={"course_code": code},
                       headers=headers("student")).status_code == 201
    assert client.get(f"/api/v1/courses/{cid}", headers=headers("student")).status_code == 200


def test_openapi_module2_routes():
    paths = app.openapi()["paths"]
    for path, method in {
        "/api/v1/courses": "post", "/api/v1/courses/join": "post",
        "/api/v1/courses/my": "get",
        "/api/v1/courses/{course_id}/teachers": "post",
        "/api/v1/courses/{course_id}/students": "post",
        "/api/v1/courses/{course_id}/students/{student_id}": "delete",
        "/api/v1/courses/{course_id}/practices": "post",
        "/api/v1/practices/{practice_id}": "patch",
        "/api/v1/practices/{practice_id}/publish": "post",
        "/api/v1/practices/{practice_id}/archive": "post",
    }.items():
        assert method in paths[path]


def test_course_create_rollback_on_commit_failure(setup, monkeypatch):
    client, db, actors, headers = setup
    code = f"ROLLBACK_{uuid4().hex[:10]}"
    original_commit = db.commit

    def fail_commit():
        raise RuntimeError("simulated commit failure")

    monkeypatch.setattr(db, "commit", fail_commit)
    from ai_grading_iot.schemas.course import CourseCreate
    from ai_grading_iot.services.course_service import CourseService
    with pytest.raises(RuntimeError):
        CourseService(db).create(CourseCreate(code=code, name="Rollback"))
    monkeypatch.setattr(db, "commit", original_commit)
    assert CourseRepository(db).get_by_code(code) is None


def test_practice_rejects_incomplete_rubrics_and_invalid_transitions(setup):
    client, db, actors, headers = setup
    code = f"IOT_{uuid4().hex[:12]}"
    cid = client.post("/api/v1/courses", json={"code": code, "name": "IoT"},
                      headers=headers("admin")).json()["id"]
    teacher_id = actors["teacher"][0].id
    client.post(f"/api/v1/courses/{cid}/teachers", json={"teacher_id": str(teacher_id)}, headers=headers("admin"))
    response = client.post(f"/api/v1/courses/{cid}/practices", json=practice_data(),
                           headers=headers("teacher"))
    pid = response.json()["practice_id"]
    assert client.patch(f"/api/v1/practices/{pid}/status", json={"status": "archived"},
                        headers=headers("teacher")).status_code == 409
    model = PracticeRepository(db).get_by_id(UUID(pid))
    RubricRepository(db).create(practice_id=model.id, rubric=Rubric(
        type=RubricType.CODE, weight=60, criteria=["Correct code"]))
    db.commit()
    assert client.patch(f"/api/v1/practices/{pid}/status", json={"status": "published"},
                        headers=headers("teacher")).status_code == 409
    assert model.status == "draft"
    assert client.get(f"/api/v1/practices/{pid}", headers=headers("teacher", 1)).status_code == 403
    assert client.delete(f"/api/v1/practices/{pid}", headers=headers("teacher")).status_code == 204


def test_course_code_my_courses_and_admin_enrollment(setup):
    client, db, actors, headers = setup
    code = f"IOT_{uuid4().hex[:12]}".upper()
    created = client.post("/api/v1/courses", json={"code": f"  {code.lower()}  ", "name": "IoT"},
                          headers=headers("admin"))
    assert created.status_code == 201
    assert created.json()["code"] == code
    cid = created.json()["id"]
    assert client.post("/api/v1/courses", json={"code": code, "name": "Duplicate"},
                       headers=headers("admin")).status_code == 409
    assert client.get("/api/v1/courses", headers=headers("student")).status_code == 403
    assert client.get("/api/v1/courses/my", headers=headers("admin")).status_code == 403
    assert client.get("/api/v1/courses/my", headers=headers("student")).json() == []
    assert client.post("/api/v1/courses/join", json={"course_code": "missing"},
                       headers=headers("student")).status_code == 404
    assert client.post("/api/v1/courses/join", json={"course_code": f"  {code.lower()}  "},
                       headers=headers("student")).status_code == 201
    assert [item["id"] for item in client.get("/api/v1/courses/my", headers=headers("student")).json()] == [cid]
    assert client.get(f"/api/v1/courses/{cid}/teachers", headers=headers("student")).status_code == 403
    assert client.post(f"/api/v1/courses/{cid}/students",
                       json={"student_id": str(actors["teacher"][0].id)},
                       headers=headers("admin")).status_code == 422
    assert client.post(f"/api/v1/courses/{cid}/students",
                       json={"student_id": str(actors["student"][1].id)},
                       headers=headers("admin")).status_code == 201
    assert client.post(f"/api/v1/courses/{cid}/students",
                       json={"student_id": str(actors["student"][1].id)},
                       headers=headers("admin")).status_code == 409
    assert len(client.get(f"/api/v1/courses/{cid}/students", headers=headers("admin")).json()) == 2
    assert client.get("/api/v1/courses/my", headers=headers("student", 1)).json()[0]["id"] == cid
    assert client.post(f"/api/v1/courses/{cid}/teachers",
                       json={"teacher_id": str(uuid4())}, headers=headers("admin")).status_code == 404
    assert client.delete(f"/api/v1/courses/{cid}/students/{uuid4()}",
                         headers=headers("admin")).status_code == 404
    assert client.patch(f"/api/v1/courses/{cid}", json={"code": "OTHER"},
                        headers=headers("admin")).status_code == 422
    assert client.patch(f"/api/v1/courses/{cid}", json={"name": "  "},
                        headers=headers("admin")).status_code == 422


def test_teacher_removal_and_student_reenrollment(setup):
    client, db, actors, headers = setup
    code = f"IOT_{uuid4().hex[:12]}".upper()
    cid = client.post("/api/v1/courses", json={"code": code, "name": "IoT"},
                      headers=headers("admin")).json()["id"]
    teacher_id = actors["teacher"][0].id
    student_id = actors["student"][0].id
    client.post(f"/api/v1/courses/{cid}/teachers", json={"teacher_id": str(teacher_id)},
                headers=headers("admin"))
    client.post("/api/v1/courses/join", json={"course_code": code}, headers=headers("student"))
    practice = client.post(f"/api/v1/courses/{cid}/practices", json=practice_data(),
                           headers=headers("teacher"))
    assert practice.status_code == 201
    pid = practice.json()["practice_id"]
    assert client.delete(f"/api/v1/courses/{cid}/teachers/{teacher_id}",
                         headers=headers("admin")).status_code == 204
    assert client.get(f"/api/v1/courses/{cid}", headers=headers("teacher")).status_code == 403
    assert client.patch(f"/api/v1/practices/{pid}", json={"title": "Changed"},
                        headers=headers("teacher")).status_code == 403
    assert client.delete(f"/api/v1/courses/{cid}/teachers/{teacher_id}",
                         headers=headers("admin")).status_code == 404
    assert client.delete(f"/api/v1/courses/{cid}/students/{student_id}",
                         headers=headers("student")).status_code == 403
    assert client.delete(f"/api/v1/courses/{cid}/students/{student_id}",
                         headers=headers("admin")).status_code == 204
    assert client.get(f"/api/v1/courses/{cid}/practices", headers=headers("student")).status_code == 403
    assert client.post("/api/v1/courses/join", json={"course_code": code},
                       headers=headers("student")).status_code == 201
    assert client.get(f"/api/v1/courses/{cid}", headers=headers("student")).status_code == 200


def test_practice_patch_and_delete_with_rubrics(setup):
    client, db, actors, headers = setup
    cid = client.post("/api/v1/courses", json={"code": f"IOT_{uuid4().hex[:12]}", "name": "IoT"},
                      headers=headers("admin")).json()["id"]
    created = client.post(f"/api/v1/courses/{cid}/practices", json=practice_data(),
                          headers=headers("admin"))
    assert created.status_code == 201
    pid = created.json()["practice_id"]
    assert created.json()["status"] == "draft"
    assert client.patch(f"/api/v1/practices/{pid}", json={"course_id": str(uuid4())},
                        headers=headers("admin")).status_code == 422
    assert client.patch(f"/api/v1/practices/{pid}", json={"rubric": {}},
                        headers=headers("admin")).status_code == 422
    updated = client.patch(f"/api/v1/practices/{pid}", json={"title": "New LED"},
                           headers=headers("admin"))
    assert updated.status_code == 200, updated.text
    assert updated.json()["title"] == "New LED"
    assert updated.json()["requirements"] == created.json()["requirements"]
    model = PracticeRepository(db).get_by_id(UUID(pid))
    rubric = RubricRepository(db).create(practice_id=model.id, rubric=Rubric(
        type=RubricType.CODE, weight=100, criteria=["Code works"]))
    db.commit()
    assert client.delete(f"/api/v1/practices/{pid}", headers=headers("admin")).status_code == 204
    assert RubricRepository(db).get_by_id(rubric.id) is None
    assert PracticeRepository(db).get_by_id(model.id) is None


def test_publish_requires_all_matching_rubric_references(setup):
    client, db, actors, headers = setup
    cid = client.post("/api/v1/courses", json={"code": f"IOT_{uuid4().hex[:12]}", "name": "IoT"},
                      headers=headers("admin")).json()["id"]
    pid = client.post(f"/api/v1/courses/{cid}/practices", json=practice_data(),
                      headers=headers("admin")).json()["practice_id"]
    model = PracticeRepository(db).get_by_id(UUID(pid))
    rubrics = [Rubric(type=kind, weight=weight, criteria=["Valid"])
               for kind, weight in [(RubricType.CODE, 50), (RubricType.DATA, 30),
                                    (RubricType.VISION, 20)]]
    for rubric in rubrics:
        RubricRepository(db).create(practice_id=model.id, rubric=rubric)
    db.commit()
    assert client.post(f"/api/v1/practices/{pid}/publish", headers=headers("admin")).status_code == 409
    model.rubric_reference = {
        "code_rubric_id": str(rubrics[0].id),
        "dashboard_rubric_id": str(rubrics[1].id),
        "vision_rubric_id": str(uuid4()),
    }
    db.commit()
    assert client.post(f"/api/v1/practices/{pid}/publish", headers=headers("admin")).status_code == 409
    model.rubric_reference = {**model.rubric_reference, "vision_rubric_id": str(rubrics[2].id)}
    RubricRepository(db).get_by_id(rubrics[2].id).weight = 19.99
    db.commit()
    assert client.post(f"/api/v1/practices/{pid}/publish", headers=headers("admin")).status_code == 409
    RubricRepository(db).get_by_id(rubrics[2].id).weight = 20
    db.commit()
    assert client.post(f"/api/v1/practices/{pid}/publish", headers=headers("admin")).status_code == 200
    assert client.post(f"/api/v1/practices/{pid}/publish", headers=headers("admin")).status_code == 409
    assert client.patch(f"/api/v1/practices/{pid}", json={"requirements": practice_data()["requirements"]},
                        headers=headers("admin")).status_code == 409
    assert client.patch(f"/api/v1/practices/{pid}", json={"title": "Published LED"},
                        headers=headers("admin")).status_code == 200
