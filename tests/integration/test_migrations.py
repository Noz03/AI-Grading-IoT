from sqlalchemy import inspect, text

import ai_grading_iot.models

from ai_grading_iot.db.base import Base
from ai_grading_iot.db.session import get_engine


def test_database_tables_exist():
    engine = get_engine()
    inspector = inspect(engine)

    database_tables = set(inspector.get_table_names())
    expected_tables = set(Base.metadata.tables.keys())

    assert expected_tables.issubset(database_tables)


def test_alembic_version_exists():
    engine = get_engine()
    inspector = inspect(engine)

    assert "alembic_version" in inspector.get_table_names()


def test_foreign_keys_exist():
    engine = get_engine()
    inspector = inspect(engine)

    practice_fks = inspector.get_foreign_keys(
        "practices"
    )

    assert any(
        fk["referred_table"] == "courses"
        for fk in practice_fks
    )

    submission_fks = inspector.get_foreign_keys(
        "submissions"
    )

    referred_tables = {
        fk["referred_table"]
        for fk in submission_fks
    }

    assert referred_tables == {
        "practices",
        "users",
    }


def test_submission_unique_constraint():
    engine = get_engine()
    inspector = inspect(engine)

    constraints = inspector.get_unique_constraints(
        "submissions"
    )

    assert any(
        set(item["column_names"])
        == {"practice_id", "student_id"}
        for item in constraints
    )


def test_database_revision_recorded():
    engine = get_engine()

    with engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()

        assert revision
