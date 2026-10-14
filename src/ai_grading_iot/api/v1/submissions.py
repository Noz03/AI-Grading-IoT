from fastapi import APIRouter

from ai_grading_iot.schemas.submission import Submission


router = APIRouter(
    tags=["Submissions"],
)


@router.post("/submissions", response_model=Submission)
def create_submission(submission: Submission):
    return submission
