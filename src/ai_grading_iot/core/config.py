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


@lru_cache
def get_settings() -> Settings:
    return Settings()
