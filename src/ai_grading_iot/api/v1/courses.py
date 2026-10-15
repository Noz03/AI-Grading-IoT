from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ai_grading_iot.api.dependencies import CurrentUser, DBSession, require_roles
from ai_grading_iot.models.user import User
from ai_grading_iot.schemas.course import (
    CourseCreate, CourseJoin, CourseResponse, CourseUpdate, MembershipResponse,
    StudentEnrollment, TeacherAssignment,
)
from ai_grading_iot.schemas.user import UserResponse
from ai_grading_iot.services.course_service import CourseConflict, CourseNotFound, CourseService, InvalidMember

router = APIRouter(prefix="/courses", tags=["Courses"])
Admin = Annotated[User, Depends(require_roles("admin"))]
Student = Annotated[User, Depends(require_roles("student"))]


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, CourseNotFound):
        return HTTPException(404, str(exc) or "Resource not found")
    if isinstance(exc, PermissionError):
        return HTTPException(403, "Insufficient permissions")
    if isinstance(exc, InvalidMember):
        return HTTPException(422, str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(422, str(exc))
    return HTTPException(409, str(exc))


@router.post("", response_model=CourseResponse, status_code=201)
def create_course(data: CourseCreate, db: DBSession, admin: Admin):
    try:
        return CourseService(db).create(data)
    except (CourseConflict, CourseNotFound) as exc:
        raise _error(exc) from exc


@router.get("", response_model=list[CourseResponse])
def list_courses(db: DBSession, admin: Admin,
                 limit: Annotated[int, Query(ge=1, le=100)] = 20,
                 offset: Annotated[int, Query(ge=0)] = 0):
    return CourseService(db).list_for(admin, limit=limit, offset=offset)


@router.post("/join", response_model=CourseResponse, status_code=201)
def join_course(data: CourseJoin, db: DBSession, student: Student):
    try:
        return CourseService(db).join(data.course_code, student)
    except (CourseNotFound, CourseConflict) as exc:
        raise _error(exc) from exc


@router.get("/my", response_model=list[CourseResponse])
def my_courses(db: DBSession, actor: CurrentUser,
               limit: Annotated[int, Query(ge=1, le=100)] = 20,
               offset: Annotated[int, Query(ge=0)] = 0):
    if actor.role not in {"teacher", "student"}:
        raise HTTPException(403, "Insufficient permissions")
    return CourseService(db).list_for(actor, limit=limit, offset=offset)


@router.get("/{course_id}", response_model=CourseResponse)
def get_course(course_id: UUID, db: DBSession, actor: CurrentUser):
    try:
        return CourseService(db).can_access(course_id, actor)
    except (CourseNotFound, PermissionError) as exc:
        raise _error(exc) from exc


@router.patch("/{course_id}", response_model=CourseResponse)
def update_course(course_id: UUID, data: CourseUpdate, db: DBSession, admin: Admin):
    try:
        return CourseService(db).update(course_id, data)
    except (CourseNotFound, ValueError) as exc:
        raise _error(exc) from exc


@router.delete("/{course_id}", status_code=204)
def delete_course(course_id: UUID, db: DBSession, admin: Admin):
    try:
        CourseService(db).delete(course_id)
    except (CourseNotFound, CourseConflict) as exc:
        raise _error(exc) from exc


@router.post("/{course_id}/teachers", response_model=MembershipResponse, status_code=201)
def assign_teacher(course_id: UUID, data: TeacherAssignment, db: DBSession, admin: Admin):
    try:
        CourseService(db).assign_teacher(course_id, data.teacher_id)
        return MembershipResponse(course_id=course_id, user_id=data.teacher_id)
    except (CourseNotFound, CourseConflict, InvalidMember) as exc:
        raise _error(exc) from exc


@router.delete("/{course_id}/teachers/{teacher_id}", status_code=204)
def remove_teacher(course_id: UUID, teacher_id: UUID, db: DBSession, admin: Admin):
    try:
        CourseService(db).remove_teacher(course_id, teacher_id)
    except (CourseNotFound, CourseConflict) as exc:
        raise _error(exc) from exc


@router.get("/{course_id}/teachers", response_model=list[UserResponse])
def list_teachers(course_id: UUID, db: DBSession, actor: CurrentUser):
    try:
        CourseService(db).can_access(course_id, actor)
        if actor.role == "student":
            raise PermissionError
        return CourseService(db).courses.get_teachers(course_id)
    except (CourseNotFound, PermissionError) as exc:
        raise _error(exc) from exc


@router.get("/{course_id}/students", response_model=list[UserResponse])
def list_students(course_id: UUID, db: DBSession, actor: CurrentUser):
    try:
        CourseService(db).can_access(course_id, actor)
        if actor.role == "student":
            raise PermissionError
        return CourseService(db).courses.get_students(course_id)
    except (CourseNotFound, PermissionError) as exc:
        raise _error(exc) from exc


@router.post("/{course_id}/students", response_model=MembershipResponse, status_code=201)
def add_student(course_id: UUID, data: StudentEnrollment, db: DBSession, admin: Admin):
    try:
        CourseService(db).add_student(course_id, data.student_id)
        return MembershipResponse(course_id=course_id, user_id=data.student_id)
    except (CourseNotFound, CourseConflict, InvalidMember) as exc:
        raise _error(exc) from exc


@router.delete("/{course_id}/students/{student_id}", status_code=204)
def remove_student(course_id: UUID, student_id: UUID, db: DBSession, admin: Admin):
    try:
        CourseService(db).remove_student(course_id, student_id)
    except (CourseNotFound, CourseConflict) as exc:
        raise _error(exc) from exc
