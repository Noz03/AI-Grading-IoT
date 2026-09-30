from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ai_grading_iot.clients.groq_client import GroqClient
from ai_grading_iot.graders.code_grader import CodeGrader
from ai_grading_iot.schemas.code_evaluation import CodeEvaluation
from ai_grading_iot.schemas.grading_result import GradingResult
from ai_grading_iot.schemas.practice import Practice
from ai_grading_iot.schemas.rubric import Rubric
from ai_grading_iot.schemas.submission import Submission

load_dotenv()

app = FastAPI(
    title="AI-Grading-IoT",
    description="AI Grading IoT - Complete Schema & Code Grader API",
    version="0.1.0",
)


class GradeCodeRequest(BaseModel):
    practice: Practice
    rubric: Rubric
    submission: Submission


class GradeCodeResponse(BaseModel):
    grading_result: GradingResult
    evaluation: CodeEvaluation


@app.get("/")
def root():
    return {
        "message": "AI-Grading-IoT API is running"
    }


@app.post("/practices")
def create_practice(practice: Practice):
    return {
        "message": "Practice schema is valid",
        "practice": practice.model_dump(mode="json"),
    }


@app.post("/rubrics")
def create_rubric(rubric: Rubric):
    return {
        "message": "Rubric schema is valid",
        "rubric": rubric.model_dump(mode="json"),
    }


@app.post("/submissions", response_model=Submission)
def create_submission(submission: Submission):
    return submission


@app.post("/grading-results", response_model=GradingResult)
def create_grading_result(grading_result: GradingResult):
    return grading_result


@app.post("/graders/code", response_model=GradeCodeResponse)
def grade_code(request: GradeCodeRequest):
    try:
        llm_client = GroqClient()
        grader = CodeGrader(llm_client=llm_client)
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
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re:
        raise HTTPException(status_code=502, detail=str(re))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống khi chấm code: {str(e)}")
