"""Lazy local YOLO11 inference on normalized original-image coordinates."""
import io
from pathlib import Path
from threading import BoundedSemaphore, Lock
from uuid import UUID

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

from ai_grading_iot.core.config import get_settings
from ai_grading_iot.schemas.vision import ImageDetections


class VisionUnavailable(Exception):
    pass


class YOLOInferenceService:
    _models: dict[str, object] = {}
    _load_lock = Lock()
    _gates: dict[str, BoundedSemaphore] = {}

    def __init__(self, model_path=None, model_factory=None):
        settings = get_settings()
        configured = Path(model_path or settings.YOLO_MODEL_PATH)
        project_root = Path(__file__).resolve().parents[3]
        self.path = (configured if configured.is_absolute() else project_root / configured).resolve()
        self.factory = model_factory
        self.settings = settings
        if not 0 <= settings.YOLO_CONFIDENCE <= 1 or not 0 <= settings.YOLO_IOU_THRESHOLD <= 1:
            raise ValueError("Invalid YOLO thresholds")
        if settings.VISION_MAX_CONCURRENT_INFERENCES < 1:
            raise ValueError("VISION_MAX_CONCURRENT_INFERENCES must be positive")

    def _model(self):
        key = str(self.path)
        with self._load_lock:
            if key not in self._models:
                if not self.path.is_file():
                    raise VisionUnavailable("Vision Grader unavailable")
                try:
                    if self.factory is None:
                        from ultralytics import YOLO
                        factory = YOLO
                    else:
                        factory = self.factory
                    self._models[key] = factory(str(self.path))
                except Exception as exc:
                    raise VisionUnavailable("Vision Grader unavailable") from exc
            self._gates.setdefault(key, BoundedSemaphore(self.settings.VISION_MAX_CONCURRENT_INFERENCES))
            return self._models[key], self._gates[key]

    def infer(self, image_id: UUID, payload: bytes) -> tuple[ImageDetections, bytes]:
        try:
            with Image.open(io.BytesIO(payload)) as source:
                source.load()
                image = source.convert("RGB")
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ValueError("Stored image integrity failure") from exc
        model, gate = self._model()
        try:
            with gate:
                result = model.predict(source=image, device=self.settings.YOLO_DEVICE,
                                       conf=self.settings.YOLO_CONFIDENCE,
                                       iou=self.settings.YOLO_IOU_THRESHOLD, verbose=False)[0]
            names = model.names
            detections = []
            for box in result.boxes:
                class_id = int(box.cls.item())
                name = names.get(class_id) if isinstance(names, dict) else names[class_id]
                if not isinstance(name, str) or not name:
                    raise ValueError("Unknown YOLO class")
                x1, y1, x2, y2 = (float(value) for value in box.xyxy[0].tolist())
                detections.append({"class_id": class_id, "class_name": name,
                                   "confidence": float(box.conf.item()),
                                   "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2}})
            output = ImageDetections(image_id=image_id, image_width=image.width,
                                     image_height=image.height, model_version=self.path.stem,
                                     detections=detections)
            annotated = image.copy()
            draw = ImageDraw.Draw(annotated)
            for detection in output.detections:
                box = detection.bbox
                draw.rectangle((box.x1, box.y1, box.x2, box.y2), outline="red", width=3)
                # Place labels above boxes where possible so detail inside boxes stays visible.
                label = f"{detection.class_name} {detection.confidence:.2f}"
                draw.text((box.x1, max(0, box.y1 - 14)), label, fill="red", font=ImageFont.load_default())
            buffer = io.BytesIO()
            annotated.save(buffer, format="PNG")
            return output, buffer.getvalue()
        except Exception as exc:
            raise RuntimeError("Vision inference failed") from exc
