from ai_grading_iot.core.config import get_settings


def test_application_settings():

    settings = get_settings()

    assert settings.APP_NAME == "AI-Grading-IoT"

    assert settings.APP_VERSION == "0.1.0"

    assert settings.API_V1_PREFIX == "/api/v1"


def test_settings_cached():

    settings_1 = get_settings()

    settings_2 = get_settings()

    assert settings_1 is settings_2

def test_database_url_configured():
    settings = get_settings()

    assert settings.DATABASE_URL is not None
    assert settings.DATABASE_URL.startswith(
        "postgresql+psycopg://"
    )
