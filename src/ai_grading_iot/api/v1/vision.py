"""Protected Submission Vision grading and artifact APIs."""
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response

from ai_grading_iot.api.dependencies import CurrentUser, DBSession
from ai_grading_iot.schemas.grading_result import GradingResult
from ai_grading_iot.services.grading_service import GradingConflict, GradingNotFound
from ai_grading_iot.services.vision_grading_service import VisionArtifactError, VisionGradingService, VisionStorageError
from ai_grading_iot.services.yolo_inference_service import VisionUnavailable

router = APIRouter(tags=["Vision Grading"])


def _error(exc):
    if isinstance(exc, GradingNotFound):
        return HTTPException(404, "Resource not found")
    if isinstance(exc, PermissionError):
        return HTTPException(403, "Insufficient permissions")
    if isinstance(exc, GradingConflict):
        return HTTPException(409, str(exc))
    if isinstance(exc, VisionStorageError):
        return HTTPException(409, "Stored Vision evidence integrity failure")
    if isinstance(exc, VisionArtifactError):
        return HTTPException(503, "Vision artifact storage unavailable")
    if isinstance(exc, VisionUnavailable):
        return HTTPException(503, "Vision Grader unavailable")
    return HTTPException(502, "Vision grading failed")


@router.post("/submissions/{submission_id}/grade-vision", response_model=GradingResult, status_code=201)
def grade_vision(submission_id: UUID, db: DBSession, actor: CurrentUser):
    try:
        return VisionGradingService(db).grade_vision(submission_id, actor)
    except (GradingNotFound, PermissionError, GradingConflict, VisionStorageError,
            VisionArtifactError, VisionUnavailable, RuntimeError, ValueError) as exc:
        raise _error(exc) from exc


@router.post("/submissions/{submission_id}/regrade-vision", response_model=GradingResult)
def regrade_vision(submission_id: UUID, db: DBSession, actor: CurrentUser):
    try:
        return VisionGradingService(db).grade_vision(submission_id, actor, regrade=True)
    except (GradingNotFound, PermissionError, GradingConflict, VisionStorageError,
            VisionArtifactError, VisionUnavailable, RuntimeError, ValueError) as exc:
        raise _error(exc) from exc


@router.get("/submissions/{submission_id}/vision-result", response_model=GradingResult)
def vision_result(submission_id: UUID, db: DBSession, actor: CurrentUser):
    try:
        return VisionGradingService(db).result(submission_id, actor)
    except (GradingNotFound, PermissionError) as exc:
        raise _error(exc) from exc


@router.get("/submissions/{submission_id}/vision-detections")
def vision_detections(submission_id: UUID, db: DBSession, actor: CurrentUser):
    try:
        return VisionGradingService(db).detections(submission_id, actor)
    except (GradingNotFound, PermissionError) as exc:
        raise _error(exc) from exc


@router.get("/submissions/{submission_id}/vision-artifacts/{image_id}")
def vision_artifact(submission_id: UUID, image_id: UUID, db: DBSession, actor: CurrentUser):
    try:
        return Response(VisionGradingService(db).artifact(submission_id, image_id, actor), media_type="image/png")
    except (GradingNotFound, PermissionError, VisionStorageError) as exc:
        raise _error(exc) from exc
