from fastapi import APIRouter
from ai_grading_iot.api.v1.auth import router as auth_router
from ai_grading_iot.api.v1.users import router as users_router
from ai_grading_iot.api.v1.courses import router as courses_router

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
from ai_grading_iot.api.v1.vision import router as vision_router


api_router = APIRouter()

api_router.include_router(auth_router)

api_router.include_router(users_router)

api_router.include_router(courses_router)

api_router.include_router(practices_router)

api_router.include_router(rubrics_router)

api_router.include_router(submissions_router)

api_router.include_router(grading_router)
api_router.include_router(vision_router)
