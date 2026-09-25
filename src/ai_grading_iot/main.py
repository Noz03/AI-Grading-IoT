from fastapi import FastAPI

from ai_grading_iot.schemas.grading_result import GradingResult
from ai_grading_iot.schemas.practice import Practice
from ai_grading_iot.schemas.rubric import Rubric
from ai_grading_iot.schemas.submission import Submission


app = FastAPI(
    title="AI-Grading-IoT",
    description="AI Grading IoT - Complete Schema API",
    version="0.1.0",
)


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
