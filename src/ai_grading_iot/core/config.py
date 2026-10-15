import os

from dataclasses import dataclass, field
from functools import lru_cache

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    APP_NAME: str = "AI-Grading-IoT"
    APP_VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"
    UPLOAD_DIR: str = field(default_factory=lambda: os.getenv("UPLOAD_DIR", "./uploads"))
    YOLO_MODEL_PATH: str = field(default_factory=lambda: os.getenv("YOLO_MODEL_PATH", "./models/yolo11_iot/best.pt"))
    YOLO_DEVICE: str = field(default_factory=lambda: os.getenv("YOLO_DEVICE", "cpu"))
    YOLO_CONFIDENCE: float = field(default_factory=lambda: float(os.getenv("YOLO_CONFIDENCE", "0.25")))
    YOLO_IOU_THRESHOLD: float = field(default_factory=lambda: float(os.getenv("YOLO_IOU_THRESHOLD", "0.45")))
    VISION_MAX_IMAGES: int = field(default_factory=lambda: int(os.getenv("VISION_MAX_IMAGES", "5")))
    VISION_MAX_CONCURRENT_INFERENCES: int = field(default_factory=lambda: int(os.getenv("VISION_MAX_CONCURRENT_INFERENCES", "1")))
    VISION_GROQ_MODEL: str | None = field(default_factory=lambda: os.getenv("VISION_GROQ_MODEL"))
    VISION_GROQ_TIMEOUT_SECONDS: float = field(default_factory=lambda: float(os.getenv("VISION_GROQ_TIMEOUT_SECONDS", "60")))

    ENVIRONMENT: str = field(
        default_factory=lambda: os.getenv(
            "ENVIRONMENT",
            "development",
        )
    )

    DATABASE_URL: str | None = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
        )
    )

    JWT_SECRET_KEY: str | None = field(
        default_factory=lambda: os.getenv("JWT_SECRET_KEY")
    )
    JWT_ACCESS_TOKEN_EXPIRE_SECONDS: int = field(
        default_factory=lambda: int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_SECONDS", "1800"))
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
