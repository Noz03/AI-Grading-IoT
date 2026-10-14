from fastapi import FastAPI

from ai_grading_iot.api.v1.router import api_router
from ai_grading_iot.core.config import get_settings


settings = get_settings()


app = FastAPI(
    title=settings.APP_NAME,
    description="AI Grading IoT - Web MVP Backend",
    version=settings.APP_VERSION,
)


app.include_router(
    api_router,
    prefix=settings.API_V1_PREFIX,
)


@app.get("/", tags=["Health"])
def root():
    return {
        "message": "AI-Grading-IoT API is running"
    }
