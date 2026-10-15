import io
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from ai_grading_iot.core.config import get_settings
from ai_grading_iot.core.security import create_access_token
from ai_grading_iot.db.session import get_db, get_engine
from ai_grading_iot.main import app
from ai_grading_iot.models.practice import Practice
from ai_grading_iot.repositories.course_repository import CourseRepository
from ai_grading_iot.repositories.grading_repository import GradingRepository
from ai_grading_iot.repositories.submission_repository import SubmissionRepository
from ai_grading_iot.repositories.user_repository import UserRepository
from ai_grading_iot.services.image_storage_service import ImageStorageService


@pytest.fixture
def context(monkeypatch, tmp_path):
    monkeypatch.setenv("JWT_SECRET_KEY", "module-four-test-secret-at-least-32-bytes")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    get_settings.cache_clear()
    with get_engine().connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint",
                     autoflush=False, expire_on_commit=False) as db:
            app.dependency_overrides[get_db] = lambda: db
            users = UserRepository(db)
            actors = {}
            for role in ("admin", "teacher", "teacher", "student", "student"):
                actor = users.create(email=f"{uuid4().hex}@example.com", password_hash="test",
                                     full_name=role, role=role)
                actors.setdefault(role, []).append(actor)
            courses = CourseRepository(db)
            course = courses.create(code=uuid4().hex, name="IoT")
            courses.assign_teacher(course_id=course.id, teacher_id=actors["teacher"][0].id)
            courses.enroll_student(course_id=course.id, student_id=actors["student"][0].id)
            practice = Practice(id=uuid4(), course_id=course.id, title="IoT", description="IoT",
                                requirements={}, environment={}, hardware=[], rubric_reference={},
                                status="published", practice_metadata={})
            db.add(practice)
            db.commit()

            def headers(role, index=0):
                return {"Authorization": f"Bearer {create_access_token(actors[role][index].id)[0]}"}

            try:
                yield TestClient(app), db, actors, headers, course, practice, tmp_path
            finally:
                app.dependency_overrides.clear()
                db.close()
                transaction.rollback()
    get_settings.cache_clear()


def draft(context, body=None):
    client, _, _, headers, _, practice, _ = context
    response = client.post(f"/api/v1/practices/{practice.id}/submissions",
                           json=body or {"code": "void setup() {}"}, headers=headers("student"))
    assert response.status_code == 201, response.text
    return response.json()["id"]


def picture(fmt):
    output = io.BytesIO()
    Image.new("RGB", (64, 64), "red").save(output, format=fmt)
    return output.getvalue()


def upload(context, submission_id, fmt="PNG", filename=None, payload=None):
    client, _, _, headers, _, _, _ = context
    ext = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[fmt]
    return client.post(f"/api/v1/submissions/{submission_id}/images",
                       files={"file": (filename or f"photo.{ext}", payload if payload is not None else picture(fmt),
                                       "application/octet-stream")}, headers=headers("student"))


def test_lifecycle_authorization_and_grading(context):
    client, db, actors, headers, course, practice, _ = context
    endpoint = f"/api/v1/practices/{practice.id}/submissions"
    assert client.post(endpoint, json={}, headers=headers("teacher")).status_code == 403
    assert client.post(endpoint, json={}, headers=headers("admin")).status_code == 403
    assert client.post(endpoint, json={}, headers=headers("student", 1)).status_code == 403
    sid = draft(context)
    assert client.post(endpoint, json={}, headers=headers("student")).status_code == 409
    assert client.get("/api/v1/submissions/my", headers=headers("student")).json()[0]["id"] == sid
    assert client.get("/api/v1/submissions/my", headers=headers("student", 1)).json() == []
    assert client.get(f"/api/v1/submissions/{sid}", headers=headers("student", 1)).status_code == 403
    assert client.get(f"/api/v1/submissions/{sid}", headers=headers("teacher", 1)).status_code == 403
    assert client.get(f"/api/v1/submissions/{sid}", headers=headers("admin")).status_code == 200
    assert len(client.get(endpoint, headers=headers("teacher")).json()) == 1
    assert client.get(endpoint, headers=headers("student")).status_code == 403
    assert client.patch(f"/api/v1/submissions/{sid}", json={"student_id": str(actors['student'][1].id)},
                        headers=headers("student")).status_code == 422
    assert client.patch(f"/api/v1/submissions/{sid}", json={"code": None},
                        headers=headers("student")).status_code == 422
    submitted = client.post(f"/api/v1/submissions/{sid}/submit", headers=headers("student"))
    assert submitted.status_code == 200
    assert submitted.json()["submitted_at"].endswith("Z")
    assert client.post(f"/api/v1/submissions/{sid}/submit", headers=headers("student")).status_code == 409
    grade = GradingRepository(db).create(submission_id=UUID(sid), code_score=80)
    db.commit()
    unchanged = client.patch(f"/api/v1/submissions/{sid}", json={"code": "void setup() {}"},
                             headers=headers("student"))
    assert unchanged.json()["status"] == "submitted"
    assert GradingRepository(db).get_by_id(grade.id) is not None
    changed = client.patch(f"/api/v1/submissions/{sid}", json={"description": "new report"},
                           headers=headers("student"))
    assert changed.json()["status"] == "draft"
    assert changed.json()["submitted_at"] is None
    assert GradingRepository(db).get_by_submission(UUID(sid)) is None
    assert client.post(f"/api/v1/submissions/{sid}/submit", headers=headers("student")).json()["id"] == sid
    courses = CourseRepository(db)
    courses.remove_student(course_id=course.id, student_id=actors["student"][0].id)
    db.commit()
    assert client.get(f"/api/v1/submissions/{sid}", headers=headers("student")).status_code == 403
    assert client.get(f"/api/v1/submissions/{sid}", headers=headers("teacher")).status_code == 200
    assert SubmissionRepository(db).get_by_id(UUID(sid)) is not None


def test_empty_and_practice_status(context):
    client, db, _, headers, _, practice, _ = context
    sid = draft(context, {"description": "  "})
    assert client.post(f"/api/v1/submissions/{sid}/submit", headers=headers("student")).status_code == 422
    practice.status = "archived"
    db.commit()
    assert client.patch(f"/api/v1/submissions/{sid}", json={"code": "x"},
                        headers=headers("student")).status_code == 409
    assert client.post(f"/api/v1/practices/{practice.id}/submissions", json={},
                       headers=headers("student")).status_code == 409


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_image_upload_access_delete(context, fmt):
    client, db, _, headers, _, _, root = context
    sid = draft(context)
    client.post(f"/api/v1/submissions/{sid}/submit", headers=headers("student"))
    grade = GradingRepository(db).create(submission_id=UUID(sid), code_score=80)
    db.commit()
    result = upload(context, sid, fmt)
    assert result.status_code == 201, result.text
    data = result.json()
    reference = SubmissionRepository(db).get_by_id(UUID(sid)).images[0]
    assert reference == f"submissions/{sid}/{data['filename']}"
    assert (root / reference).exists()
    assert GradingRepository(db).get_by_submission(UUID(sid)) is None
    assert client.get(data["url"]).status_code == 401
    assert client.get(data["url"], headers=headers("student", 1)).status_code == 403
    assert client.get(data["url"], headers=headers("teacher", 1)).status_code == 403
    for role in ("student", "teacher", "admin"):
        response = client.get(data["url"], headers=headers(role))
        assert response.status_code == 200
        assert response.headers["content-type"] == data["content_type"]
    assert client.delete(data["url"], headers=headers("teacher")).status_code == 403
    assert client.post(f"/api/v1/submissions/{sid}/submit", headers=headers("student")).status_code == 200
    second_grade = GradingRepository(db).create(submission_id=UUID(sid), code_score=90)
    db.commit()
    assert client.delete(data["url"], headers=headers("student")).status_code == 204
    assert not (root / reference).exists()
    assert SubmissionRepository(db).get_by_id(UUID(sid)).images == []
    assert SubmissionRepository(db).get_by_id(UUID(sid)).status == "draft"
    assert GradingRepository(db).get_by_id(second_grade.id) is None
    assert client.get(data["url"], headers=headers("admin")).status_code == 404


def test_image_validation_limits_and_missing_file(context, monkeypatch):
    client, db, _, headers, _, _, root = context
    sid = draft(context)
    assert upload(context, sid, filename="fake.jpg", payload=b"not an image").status_code == 415
    assert upload(context, sid, filename="fake.jpg", payload=picture("PNG")).status_code == 415
    assert upload(context, sid, payload=picture("PNG")[:-10]).status_code == 415
    pixels = picture("PNG")
    with monkeypatch.context() as patch:
        patch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
        assert upload(context, sid, payload=pixels).status_code == 415
    assert upload(context, sid, payload=b"x" * (10 * 1024 * 1024 + 1)).status_code == 413
    for _ in range(5):
        assert upload(context, sid).status_code == 201
    assert upload(context, sid).status_code == 409
    reference = SubmissionRepository(db).get_by_id(UUID(sid)).images[0]
    ImageStorageService(root).remove(reference)
    image_id = reference.rsplit("/", 1)[1].split(".")[0]
    assert client.get(f"/api/v1/submissions/{sid}/images/{image_id}",
                      headers=headers("student")).status_code == 404
    assert client.get(f"/api/v1/submissions/{sid}/images/not-a-uuid",
                      headers=headers("student")).status_code == 422


def test_upload_database_failure_cleans_file(context, monkeypatch):
    client, db, _, headers, _, _, root = context
    sid = draft(context)
    original = GradingRepository.get_by_submission

    def fail(*args, **kwargs):
        raise RuntimeError("simulated failure")

    client.post(f"/api/v1/submissions/{sid}/submit", headers=headers("student"))
    monkeypatch.setattr(GradingRepository, "get_by_submission", fail)
    with pytest.raises(RuntimeError):
        upload(context, sid)
    monkeypatch.setattr(GradingRepository, "get_by_submission", original)
    db.expire_all()
    assert SubmissionRepository(db).get_by_id(UUID(sid)).images == []
    assert list(root.rglob("*.png")) == []


def test_patch_database_failure_preserves_grading(context, monkeypatch):
    client, db, _, headers, _, _, _ = context
    sid = draft(context)
    client.post(f"/api/v1/submissions/{sid}/submit", headers=headers("student"))
    grade = GradingRepository(db).create(submission_id=UUID(sid), code_score=80)
    db.commit()
    original_commit = db.commit

    def fail_commit():
        raise RuntimeError("simulated commit failure")

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(RuntimeError):
        client.patch(f"/api/v1/submissions/{sid}", json={"code": "changed"},
                     headers=headers("student"))
    monkeypatch.setattr(db, "commit", original_commit)
    db.expire_all()
    model = SubmissionRepository(db).get_by_id(UUID(sid))
    assert model.status == "submitted"
    assert model.code == "void setup() {}"
    assert GradingRepository(db).get_by_id(grade.id) is not None


def test_image_write_and_cleanup_failure(context, monkeypatch):
    client, db, _, headers, _, _, root = context
    sid = draft(context)
    original_store = ImageStorageService.store

    def fail_store(*args):
        raise OSError("storage unavailable")

    monkeypatch.setattr(ImageStorageService, "store", fail_store)
    with pytest.raises(OSError):
        upload(context, sid)
    monkeypatch.setattr(ImageStorageService, "store", original_store)
    db.expire_all()
    assert SubmissionRepository(db).get_by_id(UUID(sid)).images == []
    assert list(root.rglob(".upload-*")) == []

    result = upload(context, sid)
    assert result.status_code == 201
    reference = SubmissionRepository(db).get_by_id(UUID(sid)).images[0]
    original_remove = ImageStorageService.remove

    def fail_remove(*args):
        raise OSError("cleanup unavailable")

    monkeypatch.setattr(ImageStorageService, "remove", fail_remove)
    assert client.delete(result.json()["url"], headers=headers("student")).status_code == 204
    monkeypatch.setattr(ImageStorageService, "remove", original_remove)
    assert SubmissionRepository(db).get_by_id(UUID(sid)).images == []
    assert (root / reference).exists()  # safe orphan, not a broken database reference


def test_failed_image_delete_keeps_reference_and_file(context, monkeypatch):
    client, db, _, headers, _, _, root = context
    sid = draft(context)
    image = upload(context, sid).json()
    reference = SubmissionRepository(db).get_by_id(UUID(sid)).images[0]
    original_commit = db.commit

    def fail_commit():
        raise RuntimeError("simulated commit failure")

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(RuntimeError):
        client.delete(image["url"], headers=headers("student"))
    monkeypatch.setattr(db, "commit", original_commit)
    db.expire_all()
    assert SubmissionRepository(db).get_by_id(UUID(sid)).images == [reference]
    assert (root / reference).exists()


def test_openapi_protection():
    paths = app.openapi()["paths"]
    for path, methods in {
        "/api/v1/practices/{practice_id}/submissions": ("get", "post"),
        "/api/v1/submissions/my": ("get",),
        "/api/v1/submissions/{submission_id}": ("get", "patch"),
        "/api/v1/submissions/{submission_id}/submit": ("post",),
        "/api/v1/submissions/{submission_id}/images": ("post",),
        "/api/v1/submissions/{submission_id}/images/{image_id}": ("get", "delete"),
    }.items():
        for method in methods:
            assert {"HTTPBearer"} <= set(paths[path][method]["security"][0])
