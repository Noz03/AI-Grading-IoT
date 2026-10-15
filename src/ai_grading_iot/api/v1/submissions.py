from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from ai_grading_iot.api.dependencies import CurrentUser, DBSession
from ai_grading_iot.schemas.submission import ImageUploaded, Submission, SubmissionCreate, SubmissionUpdate
from ai_grading_iot.services.image_storage_service import ImageStorageError
from ai_grading_iot.services.submission_service import (
    SubmissionConflict, SubmissionNotFound, SubmissionService,
)

router = APIRouter(tags=["Submissions"])


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, ImageStorageError):
        return HTTPException(exc.status_code, str(exc))
    if isinstance(exc, SubmissionNotFound):
        return HTTPException(404, "Resource not found")
    if isinstance(exc, PermissionError):
        return HTTPException(403, "Insufficient permissions")
    if isinstance(exc, SubmissionConflict):
        return HTTPException(409, str(exc))
    return HTTPException(422, str(exc))


@router.post("/practices/{practice_id}/submissions", response_model=Submission, status_code=201)
def create_draft(practice_id: UUID, data: SubmissionCreate, db: DBSession, actor: CurrentUser):
    try:
        return SubmissionService(db).create(practice_id, data, actor)
    except (SubmissionNotFound, SubmissionConflict, PermissionError) as exc:
        raise _error(exc) from exc


@router.get("/submissions/my", response_model=list[Submission])
def my_submissions(db: DBSession, actor: CurrentUser,
                   limit: Annotated[int, Query(ge=1, le=100)] = 20,
                   offset: Annotated[int, Query(ge=0)] = 0):
    try:
        return SubmissionService(db).mine(actor, limit=limit, offset=offset)
    except PermissionError as exc:
        raise _error(exc) from exc


@router.get("/practices/{practice_id}/submissions", response_model=list[Submission])
def practice_submissions(practice_id: UUID, db: DBSession, actor: CurrentUser,
                         limit: Annotated[int, Query(ge=1, le=100)] = 20,
                         offset: Annotated[int, Query(ge=0)] = 0):
    try:
        return SubmissionService(db).for_practice(practice_id, actor, limit=limit, offset=offset)
    except (SubmissionNotFound, PermissionError) as exc:
        raise _error(exc) from exc


@router.get("/submissions/{submission_id}", response_model=Submission)
def get_submission(submission_id: UUID, db: DBSession, actor: CurrentUser):
    try:
        return SubmissionService(db).get(submission_id, actor)
    except (SubmissionNotFound, PermissionError) as exc:
        raise _error(exc) from exc


@router.patch("/submissions/{submission_id}", response_model=Submission)
def update_submission(submission_id: UUID, data: SubmissionUpdate, db: DBSession, actor: CurrentUser):
    try:
        return SubmissionService(db).update(submission_id, data, actor)
    except (SubmissionNotFound, SubmissionConflict, PermissionError, ValueError, ImageStorageError) as exc:
        raise _error(exc) from exc


@router.post("/submissions/{submission_id}/submit", response_model=Submission)
def submit_submission(submission_id: UUID, db: DBSession, actor: CurrentUser):
    try:
        return SubmissionService(db).submit(submission_id, actor)
    except (SubmissionNotFound, SubmissionConflict, PermissionError, ValueError) as exc:
        raise _error(exc) from exc


@router.post("/submissions/{submission_id}/images", response_model=ImageUploaded, status_code=201)
def upload_image(submission_id: UUID, db: DBSession, actor: CurrentUser, file: UploadFile = File(...)):
    try:
        image_id, extension, content_type = SubmissionService(db).upload(submission_id, file, actor)
    except (SubmissionNotFound, SubmissionConflict, PermissionError, ImageStorageError) as exc:
        raise _error(exc) from exc
    return ImageUploaded(image_id=image_id, filename=f"{image_id}.{extension}",
                         content_type=content_type,
                         url=f"/api/v1/submissions/{submission_id}/images/{image_id}")


@router.get("/submissions/{submission_id}/images/{image_id}")
def get_image(submission_id: UUID, image_id: UUID, db: DBSession, actor: CurrentUser):
    try:
        payload, media_type = SubmissionService(db).read_image(submission_id, image_id, actor)
    except (SubmissionNotFound, PermissionError, ImageStorageError) as exc:
        raise _error(exc) from exc
    return Response(payload, media_type=media_type, headers={"Cache-Control": "private, no-store"})


@router.delete("/submissions/{submission_id}/images/{image_id}", status_code=204)
def delete_image(submission_id: UUID, image_id: UUID, db: DBSession, actor: CurrentUser):
    try:
        SubmissionService(db).delete_image(submission_id, image_id, actor)
    except (SubmissionNotFound, SubmissionConflict, PermissionError, ImageStorageError) as exc:
        raise _error(exc) from exc
