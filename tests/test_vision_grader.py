import io
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from PIL import Image
from pydantic import ValidationError

from ai_grading_iot.graders.vision_grader import VisionGrader
from ai_grading_iot.schemas.practice import Practice
from ai_grading_iot.schemas.rubric import Rubric
from ai_grading_iot.schemas.vision import ImageDetections
from ai_grading_iot.services.yolo_inference_service import YOLOInferenceService, VisionUnavailable
from ai_grading_iot.clients.groq_client import GroqClient


def png():
    buffer = io.BytesIO()
    Image.new("RGB", (80, 60), "white").save(buffer, "PNG")
    return buffer.getvalue()


def inputs(count=1):
    practice = Practice(title="IoT", description="Kit", requirements={"objective": "Connect sensor",
        "tasks": [{"order": 1, "description": "Use sensor"}]},
        environment={"board": "ESP32", "framework": "Arduino", "language": "C++"},
        rubric={}, metadata={"created_by": "test"})
    rubric = Rubric(type="vision", weight=20, criteria=["Use sensor"])
    images = [(ImageDetections(image_id=uuid4(), image_width=80, image_height=60,
                model_version="test", detections=[]), png(), png()) for _ in range(count)]
    return practice, rubric, images


class FakeGroq:
    def __init__(self):
        self.calls = []

    def generate_vision(self, prompt, images, *, model, timeout):
        self.calls.append((prompt, images, model, timeout))
        if images:
            image_id = prompt.split("image_id: ")[1].split(".")[0]
            return json.dumps({"image_id": image_id, "observations": [
                {"criterion": "Use sensor", "status": "observed", "evidence": "Visible sensor"}],
                "limitations": []})
        import re
        image_ids = re.findall(r'"image_id": "([0-9a-f-]{36})"', prompt)
        return json.dumps({"score": 85, "evidence_status": "sufficient", "feedback": "Sensor visible",
                           "criteria_feedback": [{"criterion": "Use sensor", "status": "observed",
                           "feedback": "Visible", "image_ids": image_ids[:1]}]})


def test_five_images_have_two_visual_inputs_each_and_one_aggregate():
    practice, rubric, images = inputs(5)
    client = FakeGroq()
    result, observations = VisionGrader(client, "configured-model", 60).grade(practice, rubric, images)
    assert result.score == 85 and len(observations) == 5
    assert len(client.calls) == 6
    assert all(len(call[1]) == 2 for call in client.calls[:5])
    assert client.calls[-1][1] == []
    assert all(image.startswith(b"\x89PNG") for call in client.calls[:5] for image in call[1])
    assert all(str(image[0].image_id) in client.calls[-1][0] for image in images)


def test_invalid_evaluations_and_detection_boxes():
    practice, rubric, images = inputs()
    client = FakeGroq()
    client.generate_vision = lambda *args, **kwargs: "{}"
    with pytest.raises(ValidationError):
        VisionGrader(client, "model", 60).grade(practice, rubric, images)
    with pytest.raises(ValidationError):
        ImageDetections(image_id=uuid4(), image_width=80, image_height=60,
            model_version="test", detections=[{"class_id": 1, "class_name": "sensor",
                "confidence": 0.8, "bbox": {"x1": 0, "y1": 0, "x2": 81, "y2": 20}}])


def test_yolo_lazy_cache_and_annotation(tmp_path):
    weights = tmp_path / "best.pt"
    weights.write_bytes(b"mock")
    calls = []
    class Number:
        def __init__(self, value): self.value = value
        def item(self): return self.value
    box = SimpleNamespace(cls=Number(0), conf=Number(0.9), xyxy=[SimpleNamespace(tolist=lambda: [2, 3, 20, 30])])
    class FakeModel:
        names = {0: "sensor"}
        def predict(self, **kwargs):
            calls.append(kwargs)
            return [SimpleNamespace(boxes=[box])]
    service = YOLOInferenceService(weights, lambda path: FakeModel())
    image_id = uuid4()
    first, annotated = service.infer(image_id, png())
    second, _ = service.infer(image_id, png())
    assert first.detections[0].class_name == "sensor" and first.image_width == 80
    assert first.detections[0].bbox.x2 == 20 and len(calls) == 2
    assert annotated != png()
    with pytest.raises(VisionUnavailable):
        YOLOInferenceService(tmp_path / "missing.pt").infer(image_id, png())


def test_groq_multimodal_contract_and_batch_limit():
    requests = []
    client = GroqClient.__new__(GroqClient)
    client.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kwargs: requests.append(kwargs) or SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))]))))
    assert client.generate_vision("Practice rubric", [png(), png()], model="configured-qwen", timeout=60) == '{"ok":true}'
    request = requests[0]
    assert request["model"] == "configured-qwen" and request["timeout"] == 60
    content = request["messages"][1]["content"]
    assert [item["type"] for item in content] == ["text", "image_url", "image_url"]
    assert all(item["image_url"]["url"].startswith("data:image/png;base64,") for item in content[1:])
    assert "untrusted" in request["messages"][0]["content"]
    with pytest.raises(ValueError):
        client.generate_vision("x", [png()], model="configured-qwen", timeout=60)


def test_unknown_criterion_and_invalid_aggregate_are_rejected():
    practice, rubric, images = inputs()
    client = FakeGroq()
    client.generate_vision = lambda *args, **kwargs: json.dumps({"image_id": str(images[0][0].image_id),
        "observations": [{"criterion": "Invented", "status": "observed", "evidence": "x"}], "limitations": []})
    with pytest.raises(ValueError, match="per-image"):
        VisionGrader(client, "model", 60).grade(practice, rubric, images)
    client = FakeGroq()
    original = client.generate_vision
    client.generate_vision = lambda prompt, images, **kwargs: original(prompt, images, **kwargs) if images else json.dumps({
        "score": 10, "evidence_status": "insufficient", "feedback": "No evidence", "criteria_feedback": []})
    with pytest.raises(ValidationError):
        VisionGrader(client, "model", 60).grade(practice, rubric, images)
