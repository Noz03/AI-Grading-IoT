import json

import pytest

from ai_grading_iot.graders.rubric_generator import RubricGenerationError, RubricGenerator
from ai_grading_iot.schemas.practice import (
    Practice, PracticeEnvironment, PracticeMetadata, PracticeRequirements,
    PracticeRubricReference, PracticeTask,
)


class StubClient:
    def __init__(self, payload):
        self.payload = payload

    def generate(self, prompt):
        assert "ESP32" in prompt
        return self.payload


@pytest.fixture
def practice():
    return Practice(title="LED", description="Control LED", requirements=PracticeRequirements(
        objective="Control LED", tasks=[PracticeTask(order=1, description="Wire LED")]),
        environment=PracticeEnvironment(board="ESP32", framework="Arduino", language="C++"),
        rubric=PracticeRubricReference(), metadata=PracticeMetadata(created_by="test"))


@pytest.fixture
def payload():
    return {"rubrics": [
        {"type": "code", "weight": 70, "criteria": ["Initialize LED GPIO"]},
        {"type": "data", "weight": 0, "criteria": []},
        {"type": "vision", "weight": 30, "criteria": ["Wire LED to board"]},
    ]}


def test_generate_valid_and_inapplicable(practice, payload):
    result = RubricGenerator(StubClient(json.dumps(payload))).generate(practice)
    assert [item.type.value for item in result] == ["code", "data", "vision"]
    assert result[1].criteria == []


@pytest.mark.parametrize("mutation", [
    lambda p: p["rubrics"].pop(),
    lambda p: p["rubrics"][1].update(type="code"),
    lambda p: p["rubrics"][1].update(type="unknown"),
    lambda p: p["rubrics"][0].update(weight=101),
    lambda p: p["rubrics"][0].update(weight=60),
    lambda p: p["rubrics"][0].update(criteria=[]),
    lambda p: p["rubrics"][0].update(criteria=["  "]),
    lambda p: p["rubrics"][0].update(criteria=[42]),
])
def test_reject_invalid_response(practice, payload, mutation):
    mutation(payload)
    with pytest.raises(RubricGenerationError):
        RubricGenerator(StubClient(json.dumps(payload))).generate(practice)


def test_reject_invalid_json(practice):
    with pytest.raises(RubricGenerationError):
        RubricGenerator(StubClient("not JSON")).generate(practice)
