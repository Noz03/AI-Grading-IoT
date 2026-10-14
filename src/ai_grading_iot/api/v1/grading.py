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
def create_grading_result(grading_result: GradingResult):
    return grading_result


@router.post(
    "/graders/code",
    response_model=GradeCodeResponse,
)
def grade_code(
    request: GradeCodeRequest,
    grader: Annotated[CodeGrader, Depends(get_code_grader)],
):
    try:
        grading_result, evaluation = grader.grade(
            practice=request.practice,
            rubric=request.rubric,
            submission=request.submission,
        )

        return GradeCodeResponse(
            grading_result=grading_result,
            evaluation=evaluation,
        )

    except ValueError as ve:
        raise HTTPException(
            status_code=400,
            detail=str(ve),
        )

    except RuntimeError as re:
        raise HTTPException(
            status_code=502,
            detail="Không thể hoàn thành chấm điểm AI.",
        ) from re
