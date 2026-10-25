"""Admin-only TA <-> course assignment endpoints (course_assistants table).

Not in API-SPECIFICATION.md, which documents no TA assignment model. Approved
as a project extension so TA access can be scoped to assigned courses (see
app/permissions.py). Changes are audited with the existing ``user_updated``
action and resource_type ``course_assistant``, so no audit enum value is added.
"""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import create_audit_log
from app.auth import require_roles
from app.database import get_db, get_read_db
from app.models import Course, CourseAssistant, User
from app.schemas import TAAssignmentCreate

router = APIRouter(prefix="/api/v1/admin/courses", tags=["admin"])


def _serialize_assignment(assignment: CourseAssistant, ta: User) -> dict:
    return {
        "id": assignment.id,
        "course_id": assignment.course_id,
        "user_id": ta.id,
        "email": ta.email,
        "full_name": ta.full_name,
        "is_active": ta.is_active,
        "assigned_at": assignment.created_at,
    }


def _course_or_404(db: Session, course_id: str) -> Course:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return course


def _resolve_ta(db: Session, payload: TAAssignmentCreate) -> User:
    if payload.email is not None:
        ta = db.query(User).filter(func.lower(User.email) == str(payload.email).strip().lower()).first()
    else:
        ta = db.get(User, payload.user_id)
    if not ta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if ta.role != "ta":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is not a teaching assistant")
    if not ta.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User account is inactive")
    return ta


@router.get("/{course_id}/tas")
def list_course_tas(
    course_id: str,
    current_user: User = Depends(require_roles("admin", read_only=True)),
    db: Session = Depends(get_read_db),
):
    _course_or_404(db, course_id)
    rows = (
        db.query(CourseAssistant, User)
        .join(User, User.id == CourseAssistant.user_id)
        .filter(CourseAssistant.course_id == course_id)
        .order_by(func.lower(User.full_name), User.id)
        .all()
    )
    items = [_serialize_assignment(assignment, ta) for assignment, ta in rows]
    return {"course_id": course_id, "items": items, "total": len(items)}


@router.post("/{course_id}/tas", status_code=status.HTTP_201_CREATED)
def assign_course_ta(
    course_id: str,
    payload: TAAssignmentCreate,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    _course_or_404(db, course_id)
    ta = _resolve_ta(db, payload)

    duplicate = HTTPException(status_code=status.HTTP_409_CONFLICT, detail="TA is already assigned to this course")
    if db.query(CourseAssistant.id).filter_by(course_id=course_id, user_id=ta.id).first():
        raise duplicate

    assignment = CourseAssistant(course_id=course_id, user_id=ta.id)
    db.add(assignment)
    try:
        db.flush()
    except IntegrityError:
        # Concurrent assignment won the unique (course_id, user_id) index.
        db.rollback()
        raise duplicate
    create_audit_log(
        db, "user_updated", current_user.id, assignment.id, resource_type="course_assistant",
        details={"change": "ta_assigned", "course_id": course_id, "ta_id": ta.id},
    )
    db.commit()
    db.refresh(assignment)
    return _serialize_assignment(assignment, ta)


@router.delete("/{course_id}/tas/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def unassign_course_ta(
    course_id: str,
    user_id: str,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    _course_or_404(db, course_id)
    assignment = db.query(CourseAssistant).filter_by(course_id=course_id, user_id=user_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TA assignment not found")

    create_audit_log(
        db, "user_updated", current_user.id, assignment.id, resource_type="course_assistant",
        details={"change": "ta_unassigned", "course_id": course_id, "ta_id": user_id},
    )
    db.delete(assignment)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
