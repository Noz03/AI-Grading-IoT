"""Module 6 API and persistence tests; model/provider remain mocked."""
import io
import json
from uuid import UUID, uuid4

from PIL import Image
from sqlalchemy import inspect

from ai_grading_iot.clients.groq_client import GroqClient
from ai_grading_iot.core.config import get_settings
from ai_grading_iot.db.session import get_engine
from ai_grading_iot.main import app
from ai_grading_iot.repositories.grading_repository import GradingRepository
from ai_grading_iot.repositories.submission_repository import SubmissionRepository
from ai_grading_iot.schemas.vision import ImageDetections
from ai_grading_iot.services.yolo_inference_service import YOLOInferenceService
from ai_grading_iot.services.vision_grading_service import VisionGradingService
from ai_grading_iot.services.image_storage_service import ImageStorageError, ImageStorageService
from test_module5_api import grading_context, make_submission


def configure_vision(context, monkeypatch):
    _, db, _, _, practice, _ = context
    for rubric in practice.rubrics:
        rubric.weight = {"code": 50, "data": 30, "vision": 20}[rubric.type]
        if rubric.type == "vision":
            rubric.criteria = ["Use sensor"]
    db.commit()
    monkeypatch.setenv("VISION_GROQ_MODEL", "test-vision-model")
    get_settings.cache_clear()


def image_bytes():
    output = io.BytesIO()
    Image.new("RGB", (80, 60), "white").save(output, "PNG")
    return output.getvalue()


def mock_pipeline(monkeypatch, calls):
    def infer(self, image_id, payload):
        calls.append(("yolo", image_id))
        return ImageDetections(image_id=image_id, image_width=80, image_height=60,
                               model_version="mock-yolo", detections=[]), image_bytes()
    monkeypatch.setattr(YOLOInferenceService, "infer", infer)

    def generate(self, prompt, images, *, model, timeout):
        calls.append(("groq", len(images)))
        assert model == "test-vision-model"
        if images:
            assert len(images) == 2
            image_id = prompt.split("image_id: ")[1].split(".")[0]
            return json.dumps({"image_id": image_id, "observations": [
                {"criterion": "Use sensor", "status": "observed", "evidence": "Visible sensor"}],
                "limitations": []})
        import re
        image_id = re.search(r'"image_id": "([0-9a-f-]{36})"', prompt).group(1)
        return json.dumps({"score": 85, "evidence_status": "sufficient", "feedback": "Sensor visible",
            "criteria_feedback": [{"criterion": "Use sensor", "status": "observed",
                                   "feedback": "Visible", "image_ids": [image_id]}]})
    monkeypatch.setattr(GroqClient, "generate_vision", generate)


def test_vision_api_five_images_auth_artifacts_and_merge(grading_context, monkeypatch):
    configure_vision(grading_context, monkeypatch)
    client, db, _, headers, _, code_calls = grading_context
    sid = make_submission(grading_context, submit=False)
    image_ids = []
    for _ in range(5):
        response = client.post(f"/api/v1/submissions/{sid}/images", files={"file": ("kit.png", image_bytes(), "image/png")},
                               headers=headers("student"))
        assert response.status_code == 201, response.text
        image_ids.append(response.json()["image_id"])
    client.post(f"/api/v1/submissions/{sid}/submit", headers=headers("student"))
    path = f"/api/v1/submissions/{sid}"
    assert client.post(path + "/grade-vision").status_code == 401
    assert client.post(path + "/grade-vision", headers=headers("student", 1)).status_code == 403
    assert client.post(path + "/grade-vision", headers=headers("teacher", 1)).status_code == 403
    assert client.post(path + "/regrade-vision", headers=headers("student")).status_code == 403
    code_result = client.post(path + "/grade", headers=headers("admin")).json()
    calls = []
    mock_pipeline(monkeypatch, calls)
    response = client.post(path + "/grade-vision", headers=headers("student"))
    assert response.status_code == 201, response.text
    result = response.json()
    assert (result["code_score"], result["data_score"], result["vision_score"], result["final_score"]) == (90, 80, 85, 86)
    assert result["code_evaluation"] == code_result["code_evaluation"]
    assert result["data_evaluation"] == code_result["data_evaluation"]
    assert len(code_calls) == 2 and len(calls) == 11
    assert [kind for kind, _ in calls].count("yolo") == 5
    assert [count for kind, count in calls if kind == "groq"] == [2] * 5 + [0]
    assert result["vision_evaluation"]["image_ids"] == image_ids
    assert len(client.get(path + "/vision-detections", headers=headers("student")).json()) == 5
    assert client.get(path + f"/vision-artifacts/{image_ids[0]}", headers=headers("student")).content.startswith(b"\x89PNG")
    assert client.get(path + f"/vision-artifacts/{image_ids[0]}", headers=headers("student", 1)).status_code == 403
    assert client.get(path + f"/vision-artifacts/{uuid4()}", headers=headers("student")).status_code == 404
    assert client.post(path + "/grade-vision", headers=headers("admin")).status_code == 409
    regraded = client.post(path + "/regrade-vision", headers=headers("teacher"))
    assert regraded.status_code == 200 and regraded.json()["id"] == result["id"]
    assert regraded.json()["code_evaluation"] == result["code_evaluation"]
    assert client.post(path + "/regrade", headers=headers("admin")).json()["vision_evaluation"] == regraded.json()["vision_evaluation"]
    assert GradingRepository(db).get_by_submission(UUID(sid)).vision_score == 85


def test_no_images_and_zero_weight(grading_context, monkeypatch):
    client, db, _, headers, practice, _ = grading_context
    sid = make_submission(grading_context)
    path = f"/api/v1/submissions/{sid}"
    assert client.post(path + "/grade-vision", headers=headers("admin")).status_code == 409
    configure_vision(grading_context, monkeypatch)
    response = client.post(path + "/grade-vision", headers=headers("student"))
    assert response.status_code == 201, response.text
    assert response.json()["vision_score"] is None
    assert response.json()["vision_evaluation"]["evidence_status"] == "insufficient"
    assert response.json()["final_score"] is None
    assert client.get(path + "/vision-result", headers=headers("student")).status_code == 200
    assert client.get(path + "/vision-detections").status_code == 401
    assert client.get(path + "/vision-detections", headers=headers("student")).json() == []
    assert "vision_evaluation" in {item["name"] for item in inspect(get_engine()).get_columns("grading_results")}
    paths = app.openapi()["paths"]
    for route in ("grade-vision", "regrade-vision", "vision-result", "vision-detections", "vision-artifacts/{image_id}"):
        assert f"/api/v1/submissions/{{submission_id}}/{route}" in paths


def test_failed_vision_regrade_preserves_previous_result(grading_context, monkeypatch):
    configure_vision(grading_context, monkeypatch)
    client, db, _, headers, _, _ = grading_context
    sid = make_submission(grading_context, submit=False)
    client.post(f"/api/v1/submissions/{sid}/images", files={"file": ("kit.png", image_bytes(), "image/png")},
                headers=headers("student"))
    client.post(f"/api/v1/submissions/{sid}/submit", headers=headers("student"))
    calls = []
    mock_pipeline(monkeypatch, calls)
    path = f"/api/v1/submissions/{sid}"
    original = client.post(path + "/grade-vision", headers=headers("admin")).json()
    def failure(*args, **kwargs):
        raise RuntimeError("secret provider failure")
    monkeypatch.setattr(GroqClient, "generate_vision", failure)
    response = client.post(path + "/regrade-vision", headers=headers("admin"))
    assert response.status_code == 502 and "secret" not in response.text
    assert client.get(path + "/vision-result", headers=headers("admin")).json() == original


def test_stale_vision_result_cannot_replace_code_data(grading_context, monkeypatch):
    configure_vision(grading_context, monkeypatch)
    client, db, _, headers, _, _ = grading_context
    sid = make_submission(grading_context, submit=False)
    client.post(f"/api/v1/submissions/{sid}/images", files={"file": ("kit.png", image_bytes(), "image/png")},
                headers=headers("student"))
    client.post(f"/api/v1/submissions/{sid}/submit", headers=headers("student"))
    path = f"/api/v1/submissions/{sid}"
    original = client.post(path + "/grade", headers=headers("admin")).json()
    calls = []
    mock_pipeline(monkeypatch, calls)
    previous = GroqClient.generate_vision
    def edit_during_inference(self, prompt, images, *, model, timeout):
        assert not db.in_transaction()
        if images:
            model_row = SubmissionRepository(db).get_by_id(UUID(sid))
            model_row.revision += 1
            db.commit()
        return previous(self, prompt, images, model=model, timeout=timeout)
    monkeypatch.setattr(GroqClient, "generate_vision", edit_during_inference)
    response = client.post(path + "/grade-vision", headers=headers("admin"))
    assert response.status_code == 409
    stored = GradingRepository(db).get_by_submission(UUID(sid))
    assert stored.vision_evaluation is None and stored.code_score == original["code_score"]
    assert stored.data_evaluation == original["data_evaluation"]
    artifact_root = get_settings().UPLOAD_DIR
    from pathlib import Path
    assert not list((Path(artifact_root) / "grading_artifacts").rglob("*.png"))


def test_storage_integrity_and_artifact_failure_do_not_write_grade(grading_context, monkeypatch):
    configure_vision(grading_context, monkeypatch)
    client, db, _, headers, _, _ = grading_context
    sid = make_submission(grading_context, submit=False)
    client.post(f"/api/v1/submissions/{sid}/images", files={"file": ("kit.png", image_bytes(), "image/png")},
                headers=headers("student"))
    client.post(f"/api/v1/submissions/{sid}/submit", headers=headers("student"))
    path = f"/api/v1/submissions/{sid}/grade-vision"
    original_read = ImageStorageService.read
    def missing(*args, **kwargs):
        raise ImageStorageError(404, "Image not found")
    monkeypatch.setattr(ImageStorageService, "read", missing)
    assert client.post(path, headers=headers("admin")).status_code == 409
    assert GradingRepository(db).get_by_submission(UUID(sid)) is None
    monkeypatch.setattr(ImageStorageService, "read", original_read)
    mock_pipeline(monkeypatch, [])
    def unavailable(*args, **kwargs):
        raise OSError("private storage path")
    monkeypatch.setattr(VisionGradingService, "_artifact_path", unavailable)
    failed = client.post(path, headers=headers("admin"))
    assert failed.status_code == 503 and "path" not in failed.text
    assert GradingRepository(db).get_by_submission(UUID(sid)) is None
