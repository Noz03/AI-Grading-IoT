from datetime import datetime, timezone
from uuid import UUID
import pytest

from pydantic import ValidationError

from ai_grading_iot.schemas.practice import (
    Practice,
    PracticeEnvironment,
    PracticeHardware,
    PracticeMetadata,
    PracticeRequirements,
    PracticeRubricReference,
    PracticeStatus,
    PracticeTask,
)

SAMPLE_PRACTICE_ID = UUID("00000000-0000-0000-0000-000000000099")


def create_valid_practice() -> Practice:
    return Practice(
        practice_id=SAMPLE_PRACTICE_ID,
        title="ESP32 LED Control",
        description="Điều khiển LED bằng ESP32.",
        requirements=PracticeRequirements(
            objective="Điều khiển LED bằng ESP32.",
            tasks=[
                PracticeTask(
                    id=UUID("00000000-0000-0000-0000-000000000001"),
                    order=1,
                    description="Kết nối LED với ESP32.",
                ),
                PracticeTask(
                    id=UUID("00000000-0000-0000-0000-000000000002"),
                    order=2,
                    description="Viết chương trình điều khiển LED.",
                ),
                PracticeTask(
                    id=UUID("00000000-0000-0000-0000-000000000003"),
                    order=3,
                    description="Kiểm tra trạng thái LED.",
                ),
            ],
            constraints=[
                "Sử dụng ESP32",
                "Sử dụng Arduino framework",
            ],
        ),
        environment=PracticeEnvironment(
            board="ESP32",
            framework="Arduino",
            language="C++",
            libraries=[
                "WiFi",
                "ArduinoJson",
            ],
        ),
        hardware=[
            PracticeHardware(
                id=UUID("00000000-0000-0000-0000-000000000010"),
                name="ESP32",
                type="microcontroller",
            ),
            PracticeHardware(
                id=UUID("00000000-0000-0000-0000-000000000011"),
                name="LED",
                type="output",
            ),
        ],
        rubric=PracticeRubricReference(
            code_rubric_id=UUID("00000000-0000-0000-0000-000000000020"),
            dashboard_rubric_id=UUID("00000000-0000-0000-0000-000000000021"),
            vision_rubric_id=UUID("00000000-0000-0000-0000-000000000022"),
        ),
        version="1.0",
        status=PracticeStatus.DRAFT,
        metadata=PracticeMetadata(
            created_by="teacher-001",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ),
    )


def test_create_valid_practice():
    practice = create_valid_practice()

    assert practice.practice_id == SAMPLE_PRACTICE_ID
    assert practice.title == "ESP32 LED Control"
    assert practice.description == "Điều khiển LED bằng ESP32."

    assert practice.requirements.objective == "Điều khiển LED bằng ESP32."
    assert len(practice.requirements.tasks) == 3

    assert practice.environment.board == "ESP32"
    assert practice.environment.framework == "Arduino"
    assert practice.environment.language == "C++"

    assert len(practice.hardware) == 2

    assert practice.rubric.code_rubric_id == UUID("00000000-0000-0000-0000-000000000020")

    assert practice.version == "1.0"
    assert practice.status == PracticeStatus.DRAFT

    assert practice.metadata.created_by == "teacher-001"
    assert practice.metadata.created_at is not None
    assert practice.metadata.updated_at is not None


def test_practice_model_dump():
    practice = create_valid_practice()

    data = practice.model_dump()

    assert data["practice_id"] == SAMPLE_PRACTICE_ID
    assert data["requirements"]["objective"] == "Điều khiển LED bằng ESP32."
    assert len(data["requirements"]["tasks"]) == 3
    assert data["environment"]["board"] == "ESP32"
    assert len(data["hardware"]) == 2
    assert data["rubric"]["code_rubric_id"] == UUID("00000000-0000-0000-0000-000000000020")
    assert data["version"] == "1.0"
    assert data["status"] == "draft"
    assert data["metadata"]["created_by"] == "teacher-001"


def test_practice_model_dump_json():
    practice = create_valid_practice()

    json_data = practice.model_dump_json()

    assert str(SAMPLE_PRACTICE_ID) in json_data
    assert '"title":"ESP32 LED Control"' in json_data


def test_task_requires_description():
    with pytest.raises(ValidationError):
        PracticeTask(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            order=1,
        )


def test_requirements_requires_at_least_one_task():
    with pytest.raises(ValidationError):
        PracticeRequirements(
            objective="Test",
            tasks=[],
        )


def test_invalid_version():
    with pytest.raises(ValidationError):
        Practice(
            practice_id=SAMPLE_PRACTICE_ID,
            title="Test",
            description="Test",
            requirements=PracticeRequirements(
                objective="Test",
                tasks=[
                    PracticeTask(
                        id=UUID("00000000-0000-0000-0000-000000000001"),
                        order=1,
                        description="Test",
                    )
                ],
            ),
            environment=PracticeEnvironment(
                board="ESP32",
                framework="Arduino",
                language="C++",
            ),
            hardware=[],
            rubric=PracticeRubricReference(),
            version="abc",
            metadata=PracticeMetadata(
                created_by="teacher-001",
            ),
        )


def test_invalid_status():
    with pytest.raises(ValidationError):
        Practice(
            practice_id=SAMPLE_PRACTICE_ID,
            title="Test",
            description="Test",
            requirements=PracticeRequirements(
                objective="Test",
                tasks=[
                    PracticeTask(
                        id=UUID("00000000-0000-0000-0000-000000000001"),
                        order=1,
                        description="Test",
                    )
                ],
            ),
            environment=PracticeEnvironment(
                board="ESP32",
                framework="Arduino",
                language="C++",
            ),
            hardware=[],
            rubric=PracticeRubricReference(),
            version="1.0",
            status="invalid",
            metadata=PracticeMetadata(
                created_by="teacher-001",
            ),
        )
