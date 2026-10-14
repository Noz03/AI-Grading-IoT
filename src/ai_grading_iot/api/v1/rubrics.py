from fastapi import APIRouter

from ai_grading_iot.schemas.rubric import Rubric


router = APIRouter(
    tags=["Rubrics"],
)


@router.post("/rubrics")
def create_rubric(rubric: Rubric):
    return {
        "message": "Rubric schema is valid",
        "rubric": rubric.model_dump(mode="json"),
    }
