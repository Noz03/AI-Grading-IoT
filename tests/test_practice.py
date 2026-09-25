from datetime import datetime, timezone

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


def create_valid_practice() -> Practice:
    return Practice(
        practice_id="PRACTICE-001",
        title="ESP32 LED Control",
        description="Điều khiển LED bằng ESP32.",
        requirements=PracticeRequirements(
            objective="Điều khiển LED bằng ESP32.",
            tasks=[
                PracticeTask(
                    id="REQ01",
                    description="Kết nối LED với ESP32.",
                ),
                PracticeTask(
                    id="REQ02",
                    description="Viết chương trình điều khiển LED.",
                ),
                PracticeTask(
                    id="REQ03",
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
                id="HW01",
                name="ESP32",
                type="microcontroller",
            ),
            PracticeHardware(
                id="HW02",
                name="LED",
                type="output",
            ),
        ],
        rubric=PracticeRubricReference(
            code_rubric_id="CODE-RUBRIC-001",
            dashboard_rubric_id="DATA-RUBRIC-001",
            vision_rubric_id="VISION-RUBRIC-001",
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

    assert practice.practice_id == "PRACTICE-001"
    assert practice.title == "ESP32 LED Control"
    assert practice.description == "Điều khiển LED bằng ESP32."

    assert practice.requirements.objective == "Điều khiển LED bằng ESP32."
    assert len(practice.requirements.tasks) == 3

    assert practice.environment.board == "ESP32"
    assert practice.environment.framework == "Arduino"
    assert practice.environment.language == "C++"

    assert len(practice.hardware) == 2

    assert practice.rubric.code_rubric_id == "CODE-RUBRIC-001"

    assert practice.version == "1.0"
    assert practice.status == PracticeStatus.DRAFT

    assert practice.metadata.created_by == "teacher-001"
    assert practice.metadata.created_at is not None
    assert practice.metadata.updated_at is not None


def test_practice_model_dump():
    practice = create_valid_practice()

    data = practice.model_dump()

    assert data["practice_id"] == "PRACTICE-001"
    assert data["requirements"]["objective"] == "Điều khiển LED bằng ESP32."
    assert len(data["requirements"]["tasks"]) == 3
    assert data["environment"]["board"] == "ESP32"
    assert len(data["hardware"]) == 2
    assert data["rubric"]["code_rubric_id"] == "CODE-RUBRIC-001"
    assert data["version"] == "1.0"
    assert data["status"] == "draft"
    assert data["metadata"]["created_by"] == "teacher-001"


def test_practice_model_dump_json():
    practice = create_valid_practice()

    json_data = practice.model_dump_json()

    assert '"practice_id":"PRACTICE-001"' in json_data
    assert '"title":"ESP32 LED Control"' in json_data


def test_task_requires_description():
    with pytest.raises(ValidationError):
        PracticeTask(
            id="REQ01",
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
            practice_id="PRACTICE-001",
            title="Test",
            description="Test",
            requirements=PracticeRequirements(
                objective="Test",
                tasks=[
                    PracticeTask(
                        id="REQ01",
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
            practice_id="PRACTICE-001",
            title="Test",
            description="Test",
            requirements=PracticeRequirements(
                objective="Test",
                tasks=[
                    PracticeTask(
                        id="REQ01",
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