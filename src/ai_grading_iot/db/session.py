from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ai_grading_iot.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()

    if not settings.DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL chưa được cấu hình."
        )

    return create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        expire_on_commit=False,
    )


def get_db() -> Generator[Session, None, None]:
    session_factory = get_session_factory()

    with session_factory() as session:
        yield session
