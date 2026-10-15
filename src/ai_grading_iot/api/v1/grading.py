from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ai_grading_iot.api.dependencies import get_code_grader
from ai_grading_iot.graders.code_grader import CodeGrader

from ai_grading_iot.schemas.code_evaluation import CodeEvaluation
from ai_grading_iot.schemas.grading_result import GradingResult
from ai_grading_iot.schemas.practice import Practice
from ai_grading_iot.schemas.rubric import Rubric
from ai_grading_iot.schemas.submission import Submission
from uuid import UUID
from ai_grading_iot.api.dependencies import CurrentUser, DBSession
from ai_grading_iot.services.grading_service import GradingService, GradingConflict, GradingNotFound


router = APIRouter(
    tags=["Grading"],
)


class GradeCodeRequest(BaseModel):
    practice: Practice
    rubric: Rubric
    submission: Submission


class GradeCodeResponse(BaseModel):
    grading_result: GradingResult
    evaluation: CodeEvaluation


@router.post(
    "/grading-results",
    response_model=GradingResult,
)
def create_grading_result(grading_result: GradingResult, actor: CurrentUser):
    raise HTTPException(410, "Use the Submission Grade API")


@router.post(
    "/graders/code",
    response_model=GradeCodeResponse,
)
def grade_code(
    request: GradeCodeRequest,
    grader: Annotated[CodeGrader, Depends(get_code_grader)],
    actor: CurrentUser,
):
    raise HTTPException(410, "Use the Submission Grade API")


def _handle(exc: Exception) -> HTTPException:
    if isinstance(exc, GradingNotFound):
        return HTTPException(404, "Resource not found")
    if isinstance(exc, PermissionError):
        return HTTPException(403, "Insufficient permissions")
    if isinstance(exc, GradingConflict):
        return HTTPException(409, str(exc))
    return HTTPException(502, "AI grading failed")


@router.post("/submissions/{submission_id}/grade", response_model=GradingResult, status_code=201)
def grade_submission(submission_id: UUID, db: DBSession, actor: CurrentUser):
    try:
        return GradingService(db).grade(submission_id, actor)
    except (GradingNotFound, GradingConflict, PermissionError, RuntimeError) as exc:
        raise _handle(exc) from exc


@router.post("/submissions/{submission_id}/regrade", response_model=GradingResult)
def regrade_submission(submission_id: UUID, db: DBSession, actor: CurrentUser):
    try:
        return GradingService(db).grade(submission_id, actor, regrade=True)
    except (GradingNotFound, GradingConflict, PermissionError, RuntimeError) as exc:
        raise _handle(exc) from exc


@router.get("/submissions/{submission_id}/grading-result", response_model=GradingResult)
def get_submission_result(submission_id: UUID, db: DBSession, actor: CurrentUser):
    try:
        return GradingService(db).by_submission(submission_id, actor)
    except (GradingNotFound, PermissionError) as exc:
        raise _handle(exc) from exc


@router.get("/grading-results/{result_id}", response_model=GradingResult)
def get_result(result_id: UUID, db: DBSession, actor: CurrentUser):
    try:
        return GradingService(db).by_id(result_id, actor)
    except (GradingNotFound, PermissionError) as exc:
        raise _handle(exc) from exc
