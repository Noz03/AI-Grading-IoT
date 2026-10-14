from fastapi import APIRouter

from ai_grading_iot.api.v1.practices import (
    router as practices_router,
)

from ai_grading_iot.api.v1.rubrics import (
    router as rubrics_router,
)

from ai_grading_iot.api.v1.submissions import (
    router as submissions_router,
)

from ai_grading_iot.api.v1.grading import (
    router as grading_router,
)


api_router = APIRouter()

api_router.include_router(practices_router)

api_router.include_router(rubrics_router)

api_router.include_router(submissions_router)

api_router.include_router(grading_router)
