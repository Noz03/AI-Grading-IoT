from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ai_grading_iot.api.dependencies import CurrentUser, DBSession, get_rubric_generator
from ai_grading_iot.graders.rubric_generator import RubricGenerator, RubricGenerationError
from ai_grading_iot.schemas.practice import Practice, PracticeStatus, PracticeUpdate
from ai_grading_iot.services.course_service import CourseNotFound
from ai_grading_iot.services.practice_service import PracticeConflict, PracticeNotFound, PracticeService
from ai_grading_iot.services.rubric_service import RubricConflict, RubricService

router = APIRouter(tags=["Practices"])


class PracticeStatusUpdate(BaseModel):
    status: PracticeStatus


class GenerationOutcome(BaseModel):
    status: str
    message: str


class PracticeCreated(Practice):
    rubric_generation: GenerationOutcome


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, (CourseNotFound, PracticeNotFound)):
        return HTTPException(404, "Resource not found")
    if isinstance(exc, PermissionError):
        return HTTPException(403, "Insufficient permissions")
    if isinstance(exc, ValueError):
        return HTTPException(422, str(exc))
    return HTTPException(409, str(exc))


@router.post("/courses/{course_id}/practices", response_model=PracticeCreated, status_code=201)
def create_practice_for_course(course_id: UUID, data: Practice, db: DBSession, actor: CurrentUser,
                               generator: RubricGenerator = Depends(get_rubric_generator)):
    try:
        practice = PracticeService(db).create(course_id, data, actor)
    except (CourseNotFound, PermissionError, PracticeConflict) as exc:
        raise _error(exc) from exc
    try:
        RubricService(db, generator).generate(practice.practice_id, actor)
        outcome = GenerationOutcome(status="succeeded", message="Three rubrics generated")
    except Exception:
        db.rollback()
        outcome = GenerationOutcome(status="failed", message="Rubric generation failed. Retry is available.")
    db.expire_all()
    saved = PracticeService(db).get(practice.practice_id, actor)
    return PracticeCreated(**saved.model_dump(), rubric_generation=outcome)


@router.get("/courses/{course_id}/practices", response_model=list[Practice])
def list_practices(course_id: UUID, db: DBSession, actor: CurrentUser,
                   limit: Annotated[int, Query(ge=1, le=100)] = 20,
                   offset: Annotated[int, Query(ge=0)] = 0):
    try:
        return PracticeService(db).list(course_id, actor, limit=limit, offset=offset)
    except (CourseNotFound, PermissionError) as exc:
        raise _error(exc) from exc


@router.get("/practices/{practice_id}", response_model=Practice)
def get_practice(practice_id: UUID, db: DBSession, actor: CurrentUser):
    try:
        return PracticeService(db).get(practice_id, actor)
    except (PracticeNotFound, PermissionError) as exc:
        raise _error(exc) from exc


@router.patch("/practices/{practice_id}", response_model=Practice)
def update_practice(practice_id: UUID, data: PracticeUpdate, db: DBSession, actor: CurrentUser):
    try:
        return PracticeService(db).update(practice_id, data, actor)
    except (PracticeNotFound, CourseNotFound, PermissionError, PracticeConflict, ValueError) as exc:
        raise _error(exc) from exc


@router.patch("/practices/{practice_id}/status", response_model=Practice)
def change_practice_status(practice_id: UUID, data: PracticeStatusUpdate,
                           db: DBSession, actor: CurrentUser):
    try:
        return PracticeService(db).change_status(practice_id, data.status, actor)
    except (PracticeNotFound, CourseNotFound, PermissionError, PracticeConflict) as exc:
        raise _error(exc) from exc


@router.post("/practices/{practice_id}/publish", response_model=Practice)
def publish_practice(practice_id: UUID, db: DBSession, actor: CurrentUser):
    try:
        return PracticeService(db).change_status(practice_id, PracticeStatus.PUBLISHED, actor)
    except (PracticeNotFound, CourseNotFound, PermissionError, PracticeConflict) as exc:
        raise _error(exc) from exc


@router.post("/practices/{practice_id}/archive", response_model=Practice)
def archive_practice(practice_id: UUID, db: DBSession, actor: CurrentUser):
    try:
        return PracticeService(db).change_status(practice_id, PracticeStatus.ARCHIVED, actor)
    except (PracticeNotFound, CourseNotFound, PermissionError, PracticeConflict) as exc:
        raise _error(exc) from exc


@router.delete("/practices/{practice_id}", status_code=204)
def delete_practice(practice_id: UUID, db: DBSession, actor: CurrentUser):
    try:
        PracticeService(db).delete(practice_id, actor)
    except (PracticeNotFound, CourseNotFound, PermissionError, PracticeConflict) as exc:
        raise _error(exc) from exc


@router.post("/practices")
def validate_practice(practice: Practice):
    return {
        "message": "Practice schema is valid",
        "practice": practice.model_dump(mode="json"),
    }
