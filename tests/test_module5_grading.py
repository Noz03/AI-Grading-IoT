import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ai_grading_iot.graders.data_grader import DataGrader
from ai_grading_iot.schemas.data_evaluation import DataEvaluation
from ai_grading_iot.schemas.data_evidence import DataEvidence
from ai_grading_iot.schemas.practice import Practice
from ai_grading_iot.schemas.rubric import Rubric
from ai_grading_iot.schemas.submission import Submission
from ai_grading_iot.services.score_aggregation import aggregate_scores


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def inputs(criteria=None):
    practice = Practice(title="Sensors", description="Temperature", requirements={
        "objective": "Calculate temperature", "tasks": [{"order": 1, "description": "Process sensor data"}]},
        environment={"board": "ESP32", "framework": "Arduino", "language": "C++"},
        rubric={}, metadata={"created_by": "test"})
    rubric = Rubric(type="data", weight=40, criteria=criteria or ["Calculate temperature"])
    submission = Submission(practice_id=practice.practice_id, student_id=uuid4(), code="float t = 25;",
                            description="Read sensor", data_evidence={"measurements": [{"name": "temperature",
                                                                                           "value": 25, "unit": "C"}]})
    return practice, rubric, submission


def test_data_grader_supported_and_insufficient():
    practice, rubric, submission = inputs()
    client = FakeClient(json.dumps({"score": 80, "feedback": "Matches", "criteria_feedback": [],
                                    "evidence_status": "sufficient"}))
    result = DataGrader(client).grade(practice, rubric, submission)
    assert result.score == 80
    assert "temperature" in client.prompts[0]
    assert "NOT seen" in client.prompts[0]
    client.response = json.dumps({"score": None, "feedback": "Insufficient readings", "criteria_feedback": [],
                                  "evidence_status": "insufficient"})
    assert DataGrader(client).grade(practice, rubric, submission).score is None


def test_data_grader_rejects_fabricated_image_and_malformed_response():
    practice, _, submission = inputs()
    rubric = Rubric(type="data", weight=40, criteria=["Dashboard image appearance"])
    client = FakeClient("{}")
    result = DataGrader(client).grade(practice, rubric, submission)
    assert result.evidence_status == "insufficient" and result.score is None
    assert client.prompts == []
    _, rubric, _ = inputs()
    with pytest.raises(RuntimeError):
        DataGrader(client).grade(practice, rubric, submission)
    client.response = json.dumps({"score": 0, "feedback": "Missing", "criteria_feedback": [],
                                  "evidence_status": "insufficient"})
    with pytest.raises(RuntimeError):
        DataGrader(client).grade(practice, rubric, submission)
    client.response = RuntimeError("rate limited")
    with pytest.raises(RuntimeError, match="provider unavailable"):
        DataGrader(client).grade(practice, rubric, submission)


def test_evidence_validation_limits():
    DataEvidence.model_validate({"measurements": [{"name": "temperature", "value": 0}]})
    for value in (float("nan"), float("inf"), True, "1"):
        with pytest.raises(ValidationError):
            DataEvidence.model_validate({"measurements": [{"name": "temperature", "value": value}]})
    with pytest.raises(ValidationError):
        DataEvidence.model_validate({"measurements": [{"name": "x", "value": 1}] * 101})
    with pytest.raises(ValidationError):
        DataEvidence.model_validate({"notes": "x" * 5001})
    with pytest.raises(ValidationError):
        DataEvidence.model_validate({"dashboard": {"image_ids": [str(uuid4()) for _ in range(6)]}})


def test_score_aggregation():
    weights = {"code": 60, "data": 40, "vision": 0}
    assert aggregate_scores(weights, {"code": 90, "data": 80, "vision": None}) == 86
    assert aggregate_scores(weights, {"code": 0, "data": 0, "vision": None}) == 0
    assert aggregate_scores(weights, {"code": 90, "data": None, "vision": None}) is None
    assert aggregate_scores({"code": 50, "data": 30, "vision": 20},
                            {"code": 90, "data": 80, "vision": None}) is None
    assert aggregate_scores({"code": 100, "data": 0, "vision": 0},
                            {"code": 12.345, "data": None, "vision": None}) == 12.35
    with pytest.raises(ValueError):
        aggregate_scores({"code": 60, "data": 30, "vision": 0},
                         {"code": 90, "data": 80, "vision": None})
