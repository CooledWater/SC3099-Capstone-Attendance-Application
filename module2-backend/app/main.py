"""
SAIV Backend API - Module 2

This is the skeleton implementation for the Backend API module.
Students must implement all endpoints according to the API specification.

See: docs/API-SPECIFICATION.md for complete endpoint documentation.
"""

import html
import json
import math
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import engine, Base, get_db
from app import models
from app.models import User, Course, Enrollment, Session as SessionModel, CheckIn
from app.schemas import (
    UserRegister,
    UserLogin,
    RefreshTokenRequest,
    UserUpdate,
    CourseCreate,
    CourseUpdate,
    EnrollmentCreate,
    SessionCreate,
    SessionUpdate,
    SessionStatusUpdate,
    CheckInCreate
)
from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    get_current_user,
    require_roles
)
from jose import jwt, JWTError
from app.auth import JWT_SECRET, ALGORITHM

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SAIV Backend API",
    description="Secure Attendance & Identity Verification System",
    version="1.0.0"
)

# CORS middleware - configure appropriately for your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy"}

@app.get("/db-health")
def db_health():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"database": "connected"}

@app.post("/api/v1/auth/register", status_code=status.HTTP_201_CREATED)
@app.post("/auth/register", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def register_user(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    existing_user = db.query(User).filter(
        User.email == user_data.email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    new_user = User(
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=hash_password(user_data.password),
        role=user_data.role
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "id": new_user.id,
        "email": new_user.email,
        "full_name": new_user.full_name,
        "role": new_user.role,
        "is_active": new_user.is_active
    }


@app.post("/api/v1/auth/login")
@app.post("/auth/login", include_in_schema=False)
def login_user(
    login_data: UserLogin,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        User.email == login_data.email
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not verify_password(
        login_data.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    access_token = create_access_token(
        user_id=user.id,
        role=user.role
    )
    
    refresh_token = create_refresh_token(
        user_id=user.id,
        role=user.role
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "camera_consent": user.camera_consent,
            "geolocation_consent": user.geolocation_consent,
            "face_enrolled": user.face_enrolled
        }
    }
    
@app.post("/api/v1/auth/refresh")
@app.post("/auth/refresh", include_in_schema=False)
def refresh_access_token(
    token_data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(
            token_data.refresh_token,
            JWT_SECRET,
            algorithms=[ALGORITHM]
        )

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

        user_id = payload.get("user_id")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    user = db.query(User).filter(User.id == user_id).first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    new_access_token = create_access_token(
        user_id=user.id,
        role=user.role
    )

    new_refresh_token = create_refresh_token(
        user_id=user.id,
        role=user.role
    )

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }
    
@app.get("/api/v1/users/me")
@app.get("/auth/me", include_in_schema=False)
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "camera_consent": current_user.camera_consent,
        "geolocation_consent": current_user.geolocation_consent,
        "face_enrolled": current_user.face_enrolled
    }


@app.put("/api/v1/users/me")
def update_me(
    update_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    updates = update_data.model_dump(exclude_unset=True)

    if "full_name" in updates and updates["full_name"] is not None:
        # XSS prevention: HTML-escape user-provided content before storing.
        updates["full_name"] = html.escape(updates["full_name"])

    for field, value in updates.items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)

    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "camera_consent": current_user.camera_consent,
        "geolocation_consent": current_user.geolocation_consent,
        "face_enrolled": current_user.face_enrolled
    }


@app.patch("/api/v1/admin/users/{user_id}/deactivate")
def deactivate_user(
    user_id: str,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user.is_active = False
    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "email": user.email,
        "is_active": user.is_active,
        "message": "User deactivated successfully"
    }


@app.get("/api/v1/audit/")
def list_audit_logs(
    current_user: User = Depends(require_roles("admin"))
):
    # Placeholder only: audit_logs persistence is not implemented yet (Week 3+).
    # This exists solely to gate the route to admins for RBAC testing.
    return {"items": [], "total": 0}


def _serialize_course(db: Session, course: Course) -> dict:
    instructor_name = None

    if course.instructor_id:
        instructor = db.query(User).filter(User.id == course.instructor_id).first()
        if instructor:
            instructor_name = instructor.full_name

    return {
        "id": course.id,
        "code": course.code,
        "name": course.name,
        "semester": course.semester,
        "instructor_id": course.instructor_id,
        "instructor_name": instructor_name,
        "venue_name": course.venue_name,
        "venue_latitude": course.venue_latitude,
        "venue_longitude": course.venue_longitude,
        "geofence_radius_meters": course.geofence_radius_meters,
        "require_face_recognition": course.require_face_recognition,
        "require_device_binding": course.require_device_binding,
        "risk_threshold": course.risk_threshold,
        "is_active": course.is_active,
        "created_at": course.created_at
    }


@app.post("/api/v1/courses/", status_code=status.HTTP_201_CREATED)
def create_course(
    course_data: CourseCreate,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db)
):
    existing_course = db.query(Course).filter(
        Course.code == course_data.code
    ).first()

    if existing_course:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Course code already exists"
        )

    new_course = Course(**course_data.model_dump())

    db.add(new_course)
    db.commit()
    db.refresh(new_course)

    return _serialize_course(db, new_course)


@app.get("/api/v1/courses/")
def list_courses(
    is_active: bool = True,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    query = db.query(Course).filter(Course.is_active == is_active)
    total = query.count()
    courses = query.offset(offset).limit(limit).all()

    return {
        "items": [_serialize_course(db, course) for course in courses],
        "total": total,
        "limit": limit,
        "offset": offset
    }


@app.get("/api/v1/courses/{course_id}")
def get_course(
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )

    return _serialize_course(db, course)


@app.put("/api/v1/courses/{course_id}")
def update_course(
    course_id: str,
    update_data: CourseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )

    if current_user.role != "admin" and course.instructor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )

    updates = update_data.model_dump(exclude_unset=True)

    for field, value in updates.items():
        setattr(course, field, value)

    db.commit()
    db.refresh(course)

    return _serialize_course(db, course)


def _serialize_enrollment(enrollment: Enrollment) -> dict:
    return {
        "id": enrollment.id,
        "student_id": enrollment.student_id,
        "course_id": enrollment.course_id,
        "is_active": enrollment.is_active,
        "enrolled_at": enrollment.enrolled_at
    }


def _create_enrollment(db: Session, student_id: str, course_id: str) -> Enrollment:
    student = db.query(User).filter(User.id == student_id).first()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )

    existing = db.query(Enrollment).filter(
        Enrollment.student_id == student_id,
        Enrollment.course_id == course_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student already enrolled"
        )

    new_enrollment = Enrollment(student_id=student_id, course_id=course_id)

    db.add(new_enrollment)
    db.commit()
    db.refresh(new_enrollment)

    return new_enrollment


@app.post("/api/v1/enrollments/", status_code=status.HTTP_201_CREATED)
def create_enrollment(
    enrollment_data: EnrollmentCreate,
    current_user: User = Depends(require_roles("instructor", "admin")),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(
        Course.id == enrollment_data.course_id
    ).first()

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )

    if current_user.role == "instructor" and course.instructor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )

    new_enrollment = _create_enrollment(
        db, enrollment_data.student_id, enrollment_data.course_id
    )

    return _serialize_enrollment(new_enrollment)


@app.post("/api/v1/admin/enrollments/", status_code=status.HTTP_201_CREATED)
def create_enrollment_admin(
    enrollment_data: EnrollmentCreate,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(
        Course.id == enrollment_data.course_id
    ).first()

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )

    new_enrollment = _create_enrollment(
        db, enrollment_data.student_id, enrollment_data.course_id
    )

    return _serialize_enrollment(new_enrollment)


@app.get("/api/v1/enrollments/my-enrollments")
def list_my_enrollments(
    current_user: User = Depends(require_roles("student")),
    db: Session = Depends(get_db)
):
    enrollments = db.query(Enrollment).filter(
        Enrollment.student_id == current_user.id,
        Enrollment.is_active == True
    ).all()

    results = []

    for enrollment in enrollments:
        course = db.query(Course).filter(Course.id == enrollment.course_id).first()
        if not course:
            continue

        course_data = _serialize_course(db, course)
        results.append({
            "id": enrollment.id,
            "course_id": course_data["id"],
            "course_code": course_data["code"],
            "course_name": course_data["name"],
            "semester": course_data["semester"],
            "instructor_name": course_data["instructor_name"],
            "enrolled_at": enrollment.enrolled_at,
            "is_active": enrollment.is_active
        })

    return results


@app.get("/api/v1/enrollments/course/{course_id}")
def list_course_enrollments(
    course_id: str,
    current_user: User = Depends(require_roles("instructor", "ta", "admin")),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )

    enrollments = db.query(Enrollment).filter(
        Enrollment.course_id == course_id,
        Enrollment.is_active == True
    ).all()

    students = []

    for enrollment in enrollments:
        student = db.query(User).filter(User.id == enrollment.student_id).first()
        if not student:
            continue

        students.append({
            "id": enrollment.id,
            "student_id": student.id,
            "student_email": student.email,
            "student_name": student.full_name,
            "enrolled_at": enrollment.enrolled_at,
            "is_active": enrollment.is_active,
            "face_enrolled": student.face_enrolled
        })

    return {
        "course_id": course.id,
        "course_code": course.code,
        "total_enrolled": len(students),
        "students": students
    }


def _to_naive_utc(value: datetime) -> datetime:
    """Normalize an incoming datetime to naive UTC.

    Test payloads send both timezone-aware ISO strings (e.g. "...Z") and
    naive ones; the sessions table columns are TIMESTAMP WITHOUT TIME ZONE
    (matching users/courses), and the rest of this codebase compares against
    naive datetime.utcnow() throughout (see app/auth.py). Normalizing here
    avoids a naive-vs-aware comparison crash.
    """
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _effective_venue(session: SessionModel, course: Course | None) -> dict:
    """Resolve session-level venue/geofence overrides against course defaults.

    Session values take precedence when set; otherwise fall back to the
    course's own values (course.geofence_radius_meters/risk_threshold are
    NOT NULL with DB defaults, so those two are effectively always
    resolvable - only venue_latitude/longitude can genuinely end up None,
    e.g. a course created without venue coordinates).
    """
    return {
        "latitude": (
            session.venue_latitude if session.venue_latitude is not None
            else (course.venue_latitude if course else None)
        ),
        "longitude": (
            session.venue_longitude if session.venue_longitude is not None
            else (course.venue_longitude if course else None)
        ),
        "name": (
            session.venue_name if session.venue_name is not None
            else (course.venue_name if course else None)
        ),
        "radius_meters": (
            session.geofence_radius_meters if session.geofence_radius_meters is not None
            else (course.geofence_radius_meters if course else None)
        ),
        "risk_threshold": (
            session.risk_threshold if session.risk_threshold is not None
            else (course.risk_threshold if course else None)
        ),
    }


def _serialize_session(db: Session, session: SessionModel) -> dict:
    course = db.query(Course).filter(Course.id == session.course_id).first()
    venue = _effective_venue(session, course)

    return {
        "id": session.id,
        "course_id": session.course_id,
        "instructor_id": session.instructor_id,
        "name": session.name,
        "session_type": session.session_type,
        "description": session.description,
        "status": session.status,
        "scheduled_start": session.scheduled_start,
        "scheduled_end": session.scheduled_end,
        "checkin_opens_at": session.checkin_opens_at,
        "checkin_closes_at": session.checkin_closes_at,
        "venue_latitude": venue["latitude"],
        "venue_longitude": venue["longitude"],
        "venue_name": venue["name"],
        "geofence_radius_meters": venue["radius_meters"],
        "require_liveness_check": session.require_liveness_check,
        "require_face_match": session.require_face_match,
        "risk_threshold": venue["risk_threshold"],
        "created_at": session.created_at
    }


def _serialize_session_summary(db: Session, session: SessionModel) -> dict:
    detail = _serialize_session(db, session)
    course = db.query(Course).filter(Course.id == session.course_id).first()
    total_enrolled = db.query(Enrollment).filter(
        Enrollment.course_id == session.course_id,
        Enrollment.is_active == True
    ).count()

    return {
        **detail,
        "course_code": course.code if course else None,
        "course_name": course.name if course else None,
        "total_enrolled": total_enrolled
    }


def _apply_status_transition(session: SessionModel, new_status: str) -> None:
    if new_status == "active" and session.actual_start is None:
        session.actual_start = datetime.utcnow()
    if new_status == "closed" and session.actual_end is None:
        session.actual_end = datetime.utcnow()
    session.status = new_status


@app.post("/api/v1/sessions/", status_code=status.HTTP_201_CREATED)
def create_session(
    session_data: SessionCreate,
    current_user: User = Depends(require_roles("instructor", "admin")),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == session_data.course_id).first()

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )

    scheduled_start = _to_naive_utc(session_data.scheduled_start)
    scheduled_end = _to_naive_utc(session_data.scheduled_end)

    if scheduled_start <= datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scheduled_start must be in the future"
        )

    if scheduled_end <= scheduled_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scheduled_end must be after scheduled_start"
        )

    checkin_opens_at = (
        _to_naive_utc(session_data.checkin_opens_at)
        if session_data.checkin_opens_at
        else scheduled_start - timedelta(minutes=15)
    )
    checkin_closes_at = (
        _to_naive_utc(session_data.checkin_closes_at)
        if session_data.checkin_closes_at
        else scheduled_start + timedelta(minutes=30)
    )

    if checkin_closes_at <= checkin_opens_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="checkin_closes_at must be after checkin_opens_at"
        )

    new_session = SessionModel(
        course_id=session_data.course_id,
        instructor_id=current_user.id,
        name=session_data.name,
        session_type=session_data.session_type,
        description=session_data.description,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        checkin_opens_at=checkin_opens_at,
        checkin_closes_at=checkin_closes_at,
        venue_latitude=session_data.venue_latitude,
        venue_longitude=session_data.venue_longitude,
        venue_name=session_data.venue_name,
        geofence_radius_meters=session_data.geofence_radius_meters,
        require_liveness_check=session_data.require_liveness_check,
        require_face_match=session_data.require_face_match,
        risk_threshold=session_data.risk_threshold
    )

    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    return _serialize_session(db, new_session)


@app.get("/api/v1/sessions/active")
def list_active_sessions(db: Session = Depends(get_db)):
    now = datetime.utcnow()

    sessions = db.query(SessionModel).filter(
        SessionModel.status == "active",
        SessionModel.checkin_opens_at <= now,
        SessionModel.checkin_closes_at >= now
    ).all()

    return [_serialize_session_summary(db, session) for session in sessions]


@app.get("/api/v1/sessions/")
def list_sessions(
    status_filter: str | None = Query(default=None, alias="status"),
    course_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(require_roles("instructor", "admin")),
    db: Session = Depends(get_db)
):
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    query = db.query(SessionModel)

    if status_filter:
        query = query.filter(SessionModel.status == status_filter)
    if course_id:
        query = query.filter(SessionModel.course_id == course_id)

    total = query.count()
    sessions = query.offset(offset).limit(limit).all()

    return {
        "items": [_serialize_session_summary(db, session) for session in sessions],
        "total": total,
        "limit": limit,
        "offset": offset
    }


@app.get("/api/v1/sessions/{session_id}")
def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    return _serialize_session(db, session)


@app.patch("/api/v1/sessions/{session_id}")
def update_session(
    session_id: str,
    update_data: SessionUpdate,
    current_user: User = Depends(require_roles("instructor", "admin")),
    db: Session = Depends(get_db)
):
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    if current_user.role != "admin" and session.instructor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )

    updates = update_data.model_dump(exclude_unset=True)

    for field in ("scheduled_start", "scheduled_end", "checkin_opens_at", "checkin_closes_at"):
        if updates.get(field) is not None:
            updates[field] = _to_naive_utc(updates[field])

    new_status = updates.pop("status", None)

    for field, value in updates.items():
        setattr(session, field, value)

    if new_status:
        _apply_status_transition(session, new_status)

    db.commit()
    db.refresh(session)

    return _serialize_session(db, session)


@app.patch("/api/v1/admin/sessions/{session_id}/status")
def update_session_status_admin(
    session_id: str,
    status_data: SessionStatusUpdate,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db)
):
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    old_status = session.status
    _apply_status_transition(session, status_data.status)

    db.commit()
    db.refresh(session)

    return {
        "id": session.id,
        "name": session.name,
        "status": session.status,
        "message": f"Session status changed from '{old_status}' to '{session.status}'"
    }


def _haversine_distance_meters(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Great-circle distance between two coordinates, in meters."""
    earth_radius_meters = 6371000.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return earth_radius_meters * c


def _assess_checkin_geofence(
    student_lat: float, student_lon: float, venue: dict
) -> dict:
    """Compute distance/risk/status from the geolocation signal only.

    Per API-SPECIFICATION.md's Check-in Status Logic table: risk_score is
    compared against the effective risk threshold for approved/flagged,
    independent of that - "GPS > 2x geofence" is a critical signal that
    forces rejection regardless of the computed score. No other signals
    (liveness/face/device/network) are computed this round, so geolocation
    is the sole driver of risk_score here.

    If venue latitude/longitude/radius can't be resolved (course has no
    venue configured), the geofence can't be evaluated at all: distance
    stays None and this contributes no risk, rather than penalizing the
    student for a configuration gap that isn't documented as an error case.
    """
    if venue["latitude"] is None or venue["longitude"] is None or venue["radius_meters"] is None:
        return {
            "distance_from_venue_meters": None,
            "risk_score": 0.0,
            "risk_factors": [],
            "status": "approved"
        }

    distance = _haversine_distance_meters(
        student_lat, student_lon, venue["latitude"], venue["longitude"]
    )
    radius = venue["radius_meters"]

    if radius > 0:
        # Linear risk scaling between the two documented reference points:
        # 0.0 at the venue itself, 1.0 (capped) at the "2x geofence" line
        # that API-SPECIFICATION.md already defines as the hard-reject cutoff.
        risk_score = min(distance / radius, 2.0) / 2.0
        exceeds_hard_limit = distance > 2 * radius
        outside_bounds = distance > radius
    else:
        # Degenerate zero-radius geofence: any nonzero distance is outside.
        risk_score = 1.0 if distance > 0 else 0.0
        exceeds_hard_limit = distance > 0
        outside_bounds = distance > 0

    risk_factors = []
    if outside_bounds:
        risk_factors.append({
            "type": "geo_out_of_bounds",
            "severity": "high" if exceeds_hard_limit else "medium",
            "weight": round(risk_score, 4)
        })

    effective_threshold = venue["risk_threshold"] if venue["risk_threshold"] is not None else 0.5

    if exceeds_hard_limit:
        checkin_status = "rejected"
    elif risk_score >= effective_threshold:
        checkin_status = "flagged"
    else:
        checkin_status = "approved"

    return {
        "distance_from_venue_meters": round(distance, 2),
        "risk_score": round(risk_score, 4),
        "risk_factors": risk_factors,
        "status": checkin_status
    }


def _serialize_checkin(checkin: CheckIn) -> dict:
    risk_factors = json.loads(checkin.risk_factors) if checkin.risk_factors else []

    return {
        "id": checkin.id,
        "session_id": checkin.session_id,
        "student_id": checkin.student_id,
        "status": checkin.status,
        "checked_in_at": checkin.checked_in_at,
        "latitude": checkin.latitude,
        "longitude": checkin.longitude,
        "distance_from_venue_meters": checkin.distance_from_venue_meters,
        "liveness_passed": checkin.liveness_passed,
        "liveness_score": checkin.liveness_score,
        "risk_score": checkin.risk_score,
        "risk_factors": risk_factors
    }


@app.post("/api/v1/checkins/", status_code=status.HTTP_201_CREATED)
def create_checkin(
    checkin_data: CheckInCreate,
    current_user: User = Depends(require_roles("student")),
    db: Session = Depends(get_db)
):
    session = db.query(SessionModel).filter(
        SessionModel.id == checkin_data.session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    if session.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session is not active"
        )

    now = datetime.utcnow()

    if now < session.checkin_opens_at or now > session.checkin_closes_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Check-in window is closed"
        )

    enrollment = db.query(Enrollment).filter(
        Enrollment.student_id == current_user.id,
        Enrollment.course_id == session.course_id,
        Enrollment.is_active == True
    ).first()

    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student is not enrolled in this course"
        )

    existing = db.query(CheckIn).filter(
        CheckIn.session_id == checkin_data.session_id,
        CheckIn.student_id == current_user.id
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already checked in to this session"
        )

    # Geofence-only decision logic for this round: liveness, face match,
    # device trust, and network signals are not computed yet (Week 5+),
    # so geolocation is the sole risk signal. device_fingerprint is
    # accepted (required by the frontend contract) but not yet linked to
    # a device record, since the devices table doesn't exist and device
    # management is out of scope this round.
    course = db.query(Course).filter(Course.id == session.course_id).first()
    venue = _effective_venue(session, course)
    assessment = _assess_checkin_geofence(
        checkin_data.latitude, checkin_data.longitude, venue
    )

    new_checkin = CheckIn(
        session_id=checkin_data.session_id,
        student_id=current_user.id,
        status=assessment["status"],
        checked_in_at=now,
        verified_at=now if assessment["status"] == "approved" else None,
        latitude=checkin_data.latitude,
        longitude=checkin_data.longitude,
        location_accuracy_meters=checkin_data.location_accuracy_meters,
        distance_from_venue_meters=assessment["distance_from_venue_meters"],
        risk_score=assessment["risk_score"],
        risk_factors=(
            json.dumps(assessment["risk_factors"])
            if assessment["risk_factors"] else None
        )
    )

    db.add(new_checkin)
    db.commit()
    db.refresh(new_checkin)

    return _serialize_checkin(new_checkin)


@app.get("/api/v1/checkins/my-checkins")
def list_my_checkins(
    course_id: str | None = None,
    limit: int = 50,
    current_user: User = Depends(require_roles("student")),
    db: Session = Depends(get_db)
):
    limit = max(1, min(limit, 100))

    query = db.query(CheckIn).filter(CheckIn.student_id == current_user.id)

    if course_id:
        query = query.join(
            SessionModel, CheckIn.session_id == SessionModel.id
        ).filter(SessionModel.course_id == course_id)

    checkins = query.order_by(CheckIn.checked_in_at.desc()).limit(limit).all()

    results = []

    for checkin in checkins:
        session = db.query(SessionModel).filter(
            SessionModel.id == checkin.session_id
        ).first()
        course = (
            db.query(Course).filter(Course.id == session.course_id).first()
            if session else None
        )

        results.append({
            "id": checkin.id,
            "session_id": checkin.session_id,
            "session_name": session.name if session else None,
            "course_code": course.code if course else None,
            "status": checkin.status,
            "checked_in_at": checkin.checked_in_at,
            "risk_score": checkin.risk_score
        })

    return results


@app.get("/api/v1/checkins/session/{session_id}")
def list_session_checkins(
    session_id: str,
    current_user: User = Depends(require_roles("instructor", "ta", "admin")),
    db: Session = Depends(get_db)
):
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    checkins = db.query(CheckIn).filter(CheckIn.session_id == session_id).all()

    results = []

    for checkin in checkins:
        student = db.query(User).filter(User.id == checkin.student_id).first()
        if not student:
            continue

        risk_factors = json.loads(checkin.risk_factors) if checkin.risk_factors else []

        results.append({
            "id": checkin.id,
            "student_id": checkin.student_id,
            "student_name": student.full_name,
            "student_email": student.email,
            "status": checkin.status,
            "checked_in_at": checkin.checked_in_at,
            "distance_from_venue_meters": checkin.distance_from_venue_meters,
            "risk_score": checkin.risk_score,
            "risk_factors": risk_factors,
            "liveness_passed": checkin.liveness_passed
        })

    return results


# =============================================================================
# TODO: Implement the following endpoints
# =============================================================================

# -----------------------------------------------------------------------------
# Authentication Endpoints (auth.py)
# -----------------------------------------------------------------------------
# POST /auth/register - User registration
# POST /auth/login - JWT token generation
# POST /auth/refresh - Token refresh
# POST /auth/logout - Logout
# GET /auth/me - Current user info
# PATCH /auth/me - Update user consent

# -----------------------------------------------------------------------------
# User Management Endpoints (users.py)
# -----------------------------------------------------------------------------
# GET /users - List users (admin only)
# GET /users/{id} - User details
# DELETE /users/{id} - Delete user

# -----------------------------------------------------------------------------
# Session Management Endpoints (sessions.py)
# -----------------------------------------------------------------------------
# DELETE /sessions/{id} - Delete session

# -----------------------------------------------------------------------------
# Check-in Endpoints (checkins.py)
# -----------------------------------------------------------------------------
# GET /checkins - List check-ins (with filters)
# GET /checkins/{id} - Check-in details

# -----------------------------------------------------------------------------
# Audit Log Endpoints (audit.py)
# -----------------------------------------------------------------------------
# GET /audit/logs - Retrieve audit logs
# POST /audit/logs - Create audit entry

# -----------------------------------------------------------------------------
# Admin Endpoints (admin.py) - Required for automated testing
# -----------------------------------------------------------------------------
# PATCH /admin/users/{user_id}/activate - Activate user (admin only)
# POST /admin/users/bulk - Bulk create users (admin only)

# =============================================================================
# Database Models to Implement (see DATABASE-SCHEMA.md)
# =============================================================================
# - users
# - devices
# - risksignals
# - auditlogs

# =============================================================================
# Security Requirements
# =============================================================================
# - JWT authentication with HS256
# - Bcrypt password hashing (cost >= 10)
# - Role-based access control (student, instructor, ta, admin)
# - Input validation and sanitization
# - Rate limiting
# - CORS configuration
