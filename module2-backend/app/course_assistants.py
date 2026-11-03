"""Admin-only TA assignment endpoints (course_assistants, session_assistants).

Course assignments are documented in API-SPECIFICATION.md. Session assignments
are an approved extension (2026-11-03): a TA can reach only the sessions
assigned here, and only while still assigned to the session's course (see
app/permissions.py). Changes are audited with the existing ``user_updated``
action and resource_type ``course_assistant`` / ``session_assistant``, so no
audit enum value is added.
"""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import create_audit_log
from app.auth import require_roles
from app.database import get_db, get_read_db
from app.models import Course, CourseAssistant, SessionAssistant, User
from app.models import Session as SessionModel
from app.schemas import TAAssignmentCreate, TASessionAssignmentCreate

router = APIRouter(prefix="/api/v1/admin/courses", tags=["admin"])
session_router = APIRouter(prefix="/api/v1/admin/sessions", tags=["admin"])


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

    # Removing the course assignment also revokes every session assignment in it.
    session_ids = db.query(SessionModel.id).filter(SessionModel.course_id == course_id)
    revoked = (
        db.query(SessionAssistant)
        .filter(SessionAssistant.user_id == user_id, SessionAssistant.session_id.in_(session_ids))
        .delete(synchronize_session=False)
    )
    create_audit_log(
        db, "user_updated", current_user.id, assignment.id, resource_type="course_assistant",
        details={"change": "ta_unassigned", "course_id": course_id, "ta_id": user_id,
                 "sessions_revoked": revoked},
    )
    db.delete(assignment)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _serialize_session_assignment(assignment: SessionAssistant, session: SessionModel) -> dict:
    return {
        "id": assignment.id,
        "session_id": session.id,
        "course_id": session.course_id,
        "user_id": assignment.user_id,
        "session_name": session.name,
        "status": session.status,
        "scheduled_start": session.scheduled_start,
        "scheduled_end": session.scheduled_end,
        "assigned_at": assignment.created_at,
    }


def _course_ta_or_error(db: Session, course_id: str, user_id: str, lock: bool = False) -> User:
    """The TA must exist, have the TA role and already be assigned to the course."""
    _course_or_404(db, course_id)
    ta = db.get(User, user_id)
    if not ta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if ta.role != "ta":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is not a teaching assistant")
    query = db.query(CourseAssistant).filter_by(course_id=course_id, user_id=user_id)
    if lock:
        # Serialises with course unassignment so no session row outlives it.
        query = query.with_for_update()
    if not query.first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TA is not assigned to this course")
    return ta


def _ta_session_page(db: Session, course_id: str, user_id: str) -> dict:
    rows = (
        db.query(SessionAssistant, SessionModel)
        .join(SessionModel, SessionModel.id == SessionAssistant.session_id)
        .filter(SessionAssistant.user_id == user_id, SessionModel.course_id == course_id)
        .order_by(SessionModel.scheduled_start, SessionModel.id)
        .all()
    )
    items = [_serialize_session_assignment(assignment, session) for assignment, session in rows]
    return {"course_id": course_id, "user_id": user_id, "items": items, "total": len(items)}


@router.get("/{course_id}/tas/{user_id}/sessions")
def list_ta_sessions(
    course_id: str,
    user_id: str,
    current_user: User = Depends(require_roles("admin", read_only=True)),
    db: Session = Depends(get_read_db),
):
    _course_or_404(db, course_id)
    return _ta_session_page(db, course_id, user_id)


@router.post("/{course_id}/tas/{user_id}/sessions")
def assign_ta_sessions(
    course_id: str,
    user_id: str,
    payload: TASessionAssignmentCreate,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    ta = _course_ta_or_error(db, course_id, user_id, lock=True)
    if not ta.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User account is inactive")

    requested = list(dict.fromkeys(payload.session_ids))
    sessions = {
        session.id: session
        for session in db.query(SessionModel).filter(SessionModel.id.in_(requested)).all()
    }
    missing = [session_id for session_id in requested if session_id not in sessions]
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found: " + ", ".join(missing))
    foreign = [session_id for session_id in requested if sessions[session_id].course_id != course_id]
    if foreign:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sessions must belong to this course: " + ", ".join(foreign),
        )

    existing = {
        row[0] for row in db.query(SessionAssistant.session_id)
        .filter(SessionAssistant.user_id == user_id, SessionAssistant.session_id.in_(requested))
        .all()
    }
    assigned = []
    for session_id in requested:
        if session_id in existing:
            continue
        try:
            with db.begin_nested():
                db.add(SessionAssistant(session_id=session_id, user_id=user_id))
                db.flush()
        except IntegrityError:
            # A concurrent request won the unique (session_id, user_id) index.
            existing.add(session_id)
            continue
        assigned.append(session_id)

    if assigned:
        create_audit_log(
            db, "user_updated", current_user.id, user_id, resource_type="session_assistant",
            details={"change": "ta_sessions_assigned", "course_id": course_id, "ta_id": user_id,
                     "session_ids": assigned},
        )
    db.commit()
    page = _ta_session_page(db, course_id, user_id)
    return {**page, "assigned": assigned, "already_assigned": [s for s in requested if s in existing]}


@router.delete("/{course_id}/tas/{user_id}/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def unassign_ta_session(
    course_id: str,
    user_id: str,
    session_id: str,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    _course_or_404(db, course_id)
    assignment = (
        db.query(SessionAssistant)
        .join(SessionModel, SessionModel.id == SessionAssistant.session_id)
        .filter(SessionAssistant.session_id == session_id, SessionAssistant.user_id == user_id,
                SessionModel.course_id == course_id)
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TA session assignment not found")

    create_audit_log(
        db, "user_updated", current_user.id, assignment.id, resource_type="session_assistant",
        details={"change": "ta_session_unassigned", "course_id": course_id, "ta_id": user_id,
                 "session_id": session_id},
    )
    db.delete(assignment)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@session_router.get("/{session_id}/tas")
def list_session_tas(
    session_id: str,
    current_user: User = Depends(require_roles("admin", read_only=True)),
    db: Session = Depends(get_read_db),
):
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    course_tas = {
        row[0] for row in db.query(CourseAssistant.user_id)
        .filter(CourseAssistant.course_id == session.course_id).all()
    }
    rows = (
        db.query(SessionAssistant, User)
        .join(User, User.id == SessionAssistant.user_id)
        .filter(SessionAssistant.session_id == session_id)
        .order_by(func.lower(User.full_name), User.id)
        .all()
    )
    items = [
        {
            "id": assignment.id,
            "session_id": session_id,
            "user_id": ta.id,
            "email": ta.email,
            "full_name": ta.full_name,
            "is_active": ta.is_active,
            "assigned_at": assignment.created_at,
            # False only if the course assignment was removed outside these endpoints.
            "course_assigned": ta.id in course_tas,
        }
        for assignment, ta in rows
    ]
    return {"session_id": session_id, "course_id": session.course_id, "items": items, "total": len(items)}
