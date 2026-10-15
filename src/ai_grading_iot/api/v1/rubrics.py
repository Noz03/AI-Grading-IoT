from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ai_grading_iot.api.dependencies import CurrentUser, DBSession, get_rubric_generator
from ai_grading_iot.graders.rubric_generator import RubricGenerator, RubricGenerationError
from ai_grading_iot.schemas.rubric import Rubric, RubricDetail, RubricUpdate
from ai_grading_iot.services.course_service import CourseNotFound
from ai_grading_iot.services.practice_service import PracticeNotFound
from ai_grading_iot.services.rubric_service import (
    RubricConflict, RubricNotFound, RubricPersistenceError, RubricService,
)


router = APIRouter(
    tags=["Rubrics"],
)


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, (CourseNotFound, PracticeNotFound, RubricNotFound)):
        return HTTPException(404, "Resource not found")
    if isinstance(exc, PermissionError):
        return HTTPException(403, "Insufficient permissions")
    if isinstance(exc, ValueError):
        return HTTPException(422, str(exc))
    if isinstance(exc, RubricGenerationError):
        return HTTPException(503, "Rubric generation failed; retry is available")
    if isinstance(exc, RubricPersistenceError):
        return HTTPException(503, "Rubric persistence failed; retry is available")
    return HTTPException(409, str(exc))


@router.post("/practices/{practice_id}/rubrics/generate", response_model=list[RubricDetail])
def generate_rubrics(practice_id: UUID, db: DBSession, actor: CurrentUser,
                     generator: RubricGenerator = Depends(get_rubric_generator)):
    try:
        return RubricService(db, generator).generate(practice_id, actor)
    except (CourseNotFound, PracticeNotFound, PermissionError, RubricConflict,
            RubricGenerationError, RubricPersistenceError) as exc:
        raise _error(exc) from exc


@router.post("/practices/{practice_id}/rubrics/regenerate", response_model=list[RubricDetail])
def regenerate_rubrics(practice_id: UUID, db: DBSession, actor: CurrentUser,
                       generator: RubricGenerator = Depends(get_rubric_generator)):
    try:
        return RubricService(db, generator).generate(practice_id, actor, replace=True)
    except (CourseNotFound, PracticeNotFound, PermissionError, RubricConflict,
            RubricGenerationError, RubricPersistenceError) as exc:
        raise _error(exc) from exc


@router.get("/practices/{practice_id}/rubrics", response_model=list[RubricDetail])
def list_rubrics(practice_id: UUID, db: DBSession, actor: CurrentUser):
    try:
        return RubricService(db).list(practice_id, actor)
    except (PracticeNotFound, PermissionError) as exc:
        raise _error(exc) from exc


@router.get("/rubrics/{rubric_id}", response_model=RubricDetail)
def get_rubric(rubric_id: UUID, db: DBSession, actor: CurrentUser):
    try:
        return RubricService(db).get(rubric_id, actor)
    except (RubricNotFound, PracticeNotFound, PermissionError) as exc:
        raise _error(exc) from exc


@router.patch("/rubrics/{rubric_id}", response_model=RubricDetail)
def update_rubric(rubric_id: UUID, data: RubricUpdate, db: DBSession, actor: CurrentUser):
    try:
        return RubricService(db).update(rubric_id, data, actor)
    except (RubricNotFound, PracticeNotFound, CourseNotFound, PermissionError,
            RubricConflict, RubricPersistenceError, ValueError) as exc:
        raise _error(exc) from exc


@router.post("/rubrics")
def create_rubric(rubric: Rubric):
    return {
        "message": "Rubric schema is valid",
        "rubric": rubric.model_dump(mode="json"),
    }
