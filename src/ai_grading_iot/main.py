from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse
import math

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


@app.exception_handler(RequestValidationError)
async def validation_error(_request, exc: RequestValidationError):
    # JSON parsers can represent NaN/Infinity even though JSON responses cannot.
    def safe(value):
        if isinstance(value, float) and not math.isfinite(value):
            return str(value)
        if isinstance(value, dict):
            return {key: safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [safe(item) for item in value]
        return value

    return JSONResponse({"detail": safe(jsonable_encoder(exc.errors()))}, status_code=422)


@app.get("/", tags=["Health"])
def root():
    return {
        "message": "AI-Grading-IoT API is running"
    }
