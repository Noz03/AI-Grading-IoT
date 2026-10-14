from sqlalchemy import text

from ai_grading_iot.db.session import (
    get_engine,
    get_session_factory,
)


def test_database_connection():
    engine = get_engine()

    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT 1")
        )

        assert result.scalar_one() == 1


def test_database_session():
    session_factory = get_session_factory()

    with session_factory() as session:
        result = session.execute(
            text("SELECT current_database()")
        )

        database_name = result.scalar_one()

        assert database_name == "ai_grading_iot"
