import json
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, ValidationError

from ai_grading_iot.clients.groq_client import GroqClient
from ai_grading_iot.schemas.practice import Practice
from ai_grading_iot.schemas.rubric import Rubric, RubricType


class RubricGenerationError(Exception):
    pass


class GeneratedRubric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: RubricType
    weight: float
    criteria: list[str]


class GeneratedSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rubrics: list[GeneratedRubric]


def validate_set(rubrics: list[Rubric]) -> None:
    if len(rubrics) != 3 or {item.type for item in rubrics} != set(RubricType):
        raise ValueError("Exactly one rubric of each type is required")
    if sum(Decimal(str(item.weight)) for item in rubrics) != Decimal("100"):
        raise ValueError("Rubric weights must total 100")


class RubricGenerator:
    def __init__(self, client: GroqClient | None = None):
        self.client = client

    def generate(self, practice: Practice) -> list[Rubric]:
        prompt = (
            "Generate exactly one code, one data and one vision rubric for this IoT practice. "
            "Return only JSON: {\"rubrics\": [{\"type\": \"code|data|vision\", "
            "\"weight\": number, \"criteria\": [string]}]}. "
            "Derive measurable, specific, nonduplicate criteria solely from the requirements. "
            "Do not invent requirements. For inapplicable categories use weight 0 and empty criteria. "
            "Weights must be between 0 and 100 and total 100. "
            "Practice: " + practice.model_dump_json(include={
                "title", "description", "requirements", "environment", "hardware"
            })
        )
        try:
            raw = (self.client or GroqClient()).generate(prompt)
            parsed = GeneratedSet.model_validate(json.loads(raw))
            rubrics = [Rubric.model_validate(item.model_dump()) for item in parsed.rubrics]
            validate_set(rubrics)
            return rubrics
        except (ValueError, TypeError, ValidationError) as exc:
            raise RubricGenerationError("Invalid rubric generation response") from exc
        except Exception as exc:
            raise RubricGenerationError("Rubric provider unavailable") from exc
