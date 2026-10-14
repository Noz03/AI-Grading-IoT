from fastapi import APIRouter

from ai_grading_iot.schemas.practice import Practice


router = APIRouter(
    tags=["Practices"],
)


@router.post("/practices")
def create_practice(practice: Practice):
    return {
        "message": "Practice schema is valid",
        "practice": practice.model_dump(mode="json"),
    }
