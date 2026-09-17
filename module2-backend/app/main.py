"""
SAIV Backend API - Module 2

This is the skeleton implementation for the Backend API module.
Students must implement all endpoints according to the API specification.

See: docs/API-SPECIFICATION.md for complete endpoint documentation.
"""

import html
import json
import math
import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Body, FastAPI, Depends, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import JSONResponse

from sqlalchemy import exists, func, text
from sqlalchemy.orm import Session

from app.database import engine, Base, get_db, get_read_db
from app import models
from app.models import User, Course, Enrollment, Session as SessionModel, CheckIn, Device
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
    CheckInCreate,
    FaceEnrollRequest,
    DeviceCreate,
    DeviceUpdate
)
from app.face_service import (
    face_service,
    FaceServiceValidationError,
    FaceServiceUnavailableError,
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

from app import motion

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SAIV Backend API",
    description="Secure Attendance & Identity Verification System",
    version="1.0.0"
)

app.include_router(motion.router)
app.add_middleware(motion.MotionBodyLimit)

@app.exception_handler(RequestValidationError)
async def safe_motion_validation(request: Request, exc: RequestValidationError):
    if request.url.path.startswith('/api/v1/motion/'):
        return JSONResponse(status_code=422, content={'detail': 'Invalid motion sequence. Capture again.'})
    return await request_validation_exception_handler(request, exc)


# CORS middleware - configure appropriately for your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REFRESH_COOKIE_NAME = "saiv_refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"
REFRESH_COOKIE_MAX_AGE = 7 * 24 * 60 * 60
REFRESH_COOKIE_SECURE = os.getenv("REFRESH_COOKIE_SECURE", "false").lower() == "true"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        secure=REFRESH_COOKIE_SECURE,
        samesite="lax",
        path=REFRESH_COOKIE_PATH
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        httponly=True,
        secure=REFRESH_COOKIE_SECURE,
        samesite="lax",
        path=REFRESH_COOKIE_PATH
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
    response: Response,
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
    _set_refresh_cookie(response, refresh_token)

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
    request: Request,
    response: Response,
    token_data: RefreshTokenRequest | None = Body(default=None),
    db: Session = Depends(get_db)
):
    # JSON-body support remains for the published API contract and non-browser
    # clients. Browser clients use the HttpOnly cookie and send no token body.
    refresh_token = (
        token_data.refresh_token
        if token_data is not None
        else request.cookies.get(REFRESH_COOKIE_NAME)
    )

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is required"
        )

    try:
        payload = jwt.decode(
            refresh_token,
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
    _set_refresh_cookie(response, new_refresh_token)

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }


@app.post("/api/v1/auth/logout")
@app.post("/auth/logout", include_in_schema=False)
def logout_user(response: Response):
    """End the browser session by expiring its HttpOnly refresh cookie."""
    _clear_refresh_cookie(response)
    return {"message": "Logged out successfully"}
    
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


@app.post("/api/v1/users/me/face/enroll")
def enroll_my_face(
    payload: FaceEnrollRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Enroll the caller's face via Module 3 and store only the template hash.

    See docs/API-SPECIFICATION.md "POST /users/me/face/enroll". The raw image
    is forwarded to the face service and never persisted; on success only
    ``face_embedding_hash`` (the returned template hash) and ``face_enrolled``
    are written to the user row.
    """
    if not current_user.camera_consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Camera consent is required before face enrollment"
        )

    image = payload.image.strip()
    if not image:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="image is required"
        )

    try:
        result = face_service.enroll_face(current_user.id, image, True)
    except FaceServiceValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        )
    except FaceServiceUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Face recognition service unavailable"
        )

    current_user.face_embedding_hash = result.face_template_hash
    current_user.face_enrolled = True
    db.commit()
    db.refresh(current_user)

    return {
        "success": True,
        "message": "Face enrolled successfully",
        "face_enrolled": True,
        "quality_score": result.quality_score
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


def _serialize_course(
    db: Session, course: Course, instructor_names: dict | None = None
) -> dict:
    instructor_name = None

    if course.instructor_id:
        if instructor_names is not None:
            # Batch-resolved by the caller (list endpoint) - no per-row query.
            instructor_name = instructor_names.get(course.instructor_id)
        else:
            instructor = db.query(User).filter(
                User.id == course.instructor_id
            ).first()
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

    # Single round trip: page of courses, each course's instructor name
    # (LEFT JOIN instead of a separate batch SELECT), and the total
    # matching count (COUNT(*) OVER() window column instead of a separate
    # query.count()) all come back together.
    rows = (
        db.query(Course, User.full_name, func.count().over().label("total_count"))
        .outerjoin(User, Course.instructor_id == User.id)
        .filter(Course.is_active == is_active)
        .order_by(Course.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    if rows:
        total = rows[0][2]
    else:
        # COUNT(*) OVER() only appears on returned rows, so an out-of-range
        # offset (or a genuinely empty result set) leaves no row to read it
        # from - fall back to a plain count() only in that rare case.
        total = db.query(Course).filter(Course.is_active == is_active).count()

    instructor_names = {
        course.instructor_id: full_name
        for course, full_name, _ in rows
        if course.instructor_id and full_name is not None
    }

    return {
        "items": [
            _serialize_course(db, course, instructor_names) for course, _, _ in rows
        ],
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
        "require_motion_check": motion.required(db, session.id),
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
    db.flush()
    if session_data.require_motion_check:
        db.add(motion.MotionPolicy(session_id=new_session.id, required=True))
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

    motion_required = updates.pop("require_motion_check", None)
    if motion_required is not None:
        policy = db.get(motion.MotionPolicy, session.id)
        if policy is None:
            policy = motion.MotionPolicy(session_id=session.id)
            db.add(policy)
        policy.required = motion_required

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
    student_lat: float,
    student_lon: float,
    venue: dict,
    accuracy: float | None = None,
) -> dict:
    """Compute the venue-distance portion of the check-in risk decision.

    This owns exactly the signals Module 2 alone can compute (the face
    service never sees the venue), per docs/prd.md sections F-GEO-1..4 and
    the API-SPECIFICATION.md Check-in Status Logic table:

    * ``distance_from_venue_meters`` - Haversine great-circle distance from
      the effective venue coordinates (F-GEO-1).
    * Within ``geofence_radius_meters``: no geo risk contribution.
      Beyond the radius but within 2x: a ``geo_out_of_bounds`` signal that
      pushes the check-in toward ``flagged`` (F-GEO-2).
    * Beyond 2x the radius: ``hard_reject`` is set - this rejection cannot
      be overridden by any other signal (F-GEO-2 / status logic table).
    * Poor GPS accuracy raises ``geo_accuracy_low`` (F-GEO-4).

    ``hard_reject`` and ``risk_score`` are returned for the caller to fuse
    with the biometric signals; ``status`` is advisory only.

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
            "hard_reject": False,
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

    # F-GEO-4: "Poor GPS accuracy raises geo_accuracy_low." No doc or test
    # defines the numeric threshold or its risk weight, so the only
    # non-arbitrary rule available is derived from the one documented
    # distance value in play: the accuracy circle is "low" once it is
    # larger than the geofence itself (the fix is too uncertain to trust
    # for the geofence decision). It is recorded as an informational
    # signal with weight 0.0 - it does not by itself move the risk score
    # or the accept/reject outcome. Any risk from GPS accuracy that DOES
    # affect the score comes from the face service's /risk/assess
    # geolocation signal, which docs/API-SPECIFICATION.md does quantify.
    if accuracy is not None and accuracy > 0 and accuracy > radius > 0:
        risk_factors.append({
            "type": "geo_accuracy_low",
            "severity": "medium",
            "weight": 0.0
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
        "hard_reject": exceeds_hard_limit,
        "status": checkin_status
    }


def _severity_for_weight(weight: float) -> str:
    """Map a 0-1 risk contribution to the documented severity buckets."""
    if weight >= 0.7:
        return "critical"
    if weight >= 0.5:
        return "high"
    if weight >= 0.3:
        return "medium"
    return "low"


def _run_biometric_verification(
    session: SessionModel, user: User, checkin_data: CheckInCreate
) -> dict:
    """Call Module 3 for the biometric signals this session requires.

    Module 1 currently sends a single base64 frame in
    ``liveness_challenge_response`` and no separate face-match image or
    ``challenge_type`` (see the cross-module contract gap noted in the PR
    description). From Module 2 the only correct options are therefore:

    * liveness: call ``/liveness/check`` with that frame and the default
      ``passive`` challenge, only when the session sets
      ``require_liveness_check`` AND a frame was actually sent.
    * face match: reuse the same frame against the user's stored
      ``face_embedding_hash`` via ``/face/verify``, only when the session
      sets ``require_face_match`` AND the user has an enrolled template.

    When a required check cannot be performed (no frame, no enrolled
    template, or the service is unreachable) the result is "not performed"
    - the column stays ``None`` and the check-in is NOT rejected on that
    basis. A pass is never fabricated.
    """
    image = (checkin_data.liveness_challenge_response or "").strip() or None

    liveness = None
    if session.require_liveness_check and image:
        liveness = face_service.check_liveness(image, "passive")

    face_match = None
    if session.require_face_match and image and user.face_embedding_hash:
        face_match = face_service.verify_face(image, user.face_embedding_hash)

    # Ask the face service to convert whatever biometric scores we have
    # into a weighted risk score (architecture.md 5.1: "the face service
    # owns signal-to-risk conversion ... the backend owns the decision").
    module3_risk = None
    liveness_score = liveness.score if liveness else None
    face_score = face_match.score if face_match else None
    if liveness_score is not None or face_score is not None:
        signals: dict = {}
        if liveness_score is not None:
            signals["liveness_score"] = liveness_score
        if face_score is not None:
            signals["face_match_score"] = face_score
        signals["geolocation"] = {
            "latitude": checkin_data.latitude,
            "longitude": checkin_data.longitude,
            "accuracy": (
                checkin_data.location_accuracy_meters
                if checkin_data.location_accuracy_meters is not None
                else 0.0
            ),
        }
        module3_risk = face_service.assess_risk(signals)

    # Persist the current-frame template hash when the service returned one
    # (face-match response first, else the liveness response).
    face_embedding_hash = None
    if face_match and face_match.face_embedding_hash:
        face_embedding_hash = face_match.face_embedding_hash
    elif liveness and liveness.face_embedding_hash:
        face_embedding_hash = liveness.face_embedding_hash

    return {
        "liveness": liveness,
        "face_match": face_match,
        "module3_risk": module3_risk,
        "face_embedding_hash": face_embedding_hash,
    }


def _combine_checkin_assessment(
    geo_assessment: dict, bio: dict, effective_threshold: float
) -> dict:
    """Fuse the geofence and biometric signals into the final decision.

    * Combined risk = ``max`` of the venue-distance risk (Module 2's own)
      and the face service's ``/risk/assess`` score. The two are
      independent views - the face service never sees the venue and Module
      2 never sees the biometric internals - and no doc specifies a
      weighting between them, so the stronger signal wins rather than being
      diluted. When no biometric check ran this is exactly the Week 4
      geofence-only score.
    * Hard rejections that no score can override (architecture.md 5.1 /
      prd.md status table): GPS beyond 2x the geofence, or a liveness check
      that was performed and failed.
    * Otherwise: ``flagged`` at/above the effective threshold, else
      ``approved``.
    """
    risk_values = [geo_assessment["risk_score"]]
    risk_factors = list(geo_assessment["risk_factors"])

    liveness = bio["liveness"]
    face_match = bio["face_match"]
    module3_risk = bio["module3_risk"]

    if module3_risk is not None:
        risk_values.append(module3_risk.risk_score)

    if liveness is not None and liveness.passed is False:
        risk_factors.append({
            "type": "liveness_failed",
            "severity": "high",
            "weight": round(1.0 - (liveness.score or 0.0), 4),
        })
    if face_match is not None and face_match.passed is False:
        weight = round(1.0 - (face_match.score or 0.0), 4)
        risk_factors.append({
            "type": "face_match_failed",
            "severity": _severity_for_weight(weight),
            "weight": weight,
        })

    combined_risk = round(max(0.0, min(1.0, max(risk_values))), 4)

    if geo_assessment["hard_reject"]:
        checkin_status = "rejected"
    elif liveness is not None and liveness.passed is False:
        checkin_status = "rejected"
    elif combined_risk >= effective_threshold:
        checkin_status = "flagged"
    else:
        checkin_status = "approved"

    return {
        "status": checkin_status,
        "risk_score": combined_risk,
        "risk_factors": risk_factors,
    }


@app.post("/api/v1/checkins/", status_code=status.HTTP_201_CREATED)
def create_checkin(
    checkin_data: CheckInCreate,
    current_user: User = Depends(require_roles("student")),
    db: Session = Depends(get_db)
):
    # Session, its course, and the enrollment/duplicate-checkin flags all in
    # one round trip: each network round trip to the (remote) database costs
    # far more than the extra correlated-subquery work, so folding the
    # membership check into the same query as the session/course lookup
    # (instead of a second round trip once the session is known) is a real
    # latency win here, not just a query-count nicety.
    enrollment_exists = (
        exists()
        .where(Enrollment.student_id == current_user.id)
        .where(Enrollment.course_id == SessionModel.course_id)
        .where(Enrollment.is_active == True)  # noqa: E712
    )
    duplicate_exists = (
        exists()
        .where(CheckIn.session_id == SessionModel.id)
        .where(CheckIn.student_id == current_user.id)
    )

    row = (
        db.query(SessionModel, Course, enrollment_exists, duplicate_exists, motion.MotionPolicy.required)
        .outerjoin(Course, SessionModel.course_id == Course.id)
        .outerjoin(motion.MotionPolicy, motion.MotionPolicy.session_id == SessionModel.id)
        .filter(SessionModel.id == checkin_data.session_id)
        .first()
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    session, course, has_active_enrollment, has_duplicate_checkin, requires_motion = row

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

    if not has_active_enrollment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student is not enrolled in this course"
        )

    if has_duplicate_checkin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already checked in to this session"
        )

    # Decision inputs: (1) the venue-distance geofence, which only Module 2
    # can compute, and (2) the biometric signals the session requires,
    # obtained from Module 3 via app.face_service. device trust / network
    # heuristics and the risk_signals table remain out of scope this round;
    # device_fingerprint is accepted per the frontend contract but not yet
    # linked to a device record.
    venue = _effective_venue(session, course)
    geo_assessment = _assess_checkin_geofence(
        checkin_data.latitude,
        checkin_data.longitude,
        venue,
        accuracy=checkin_data.location_accuracy_meters,
    )
    if checkin_data.motion_verification_id:
        biometrics = motion.consume(db, current_user, session.id, checkin_data.motion_verification_id)
    elif requires_motion:
        raise HTTPException(400, "Complete the motion challenge before checking in")
    else:
        biometrics = _run_biometric_verification(session, current_user, checkin_data)

    effective_threshold = (
        venue["risk_threshold"] if venue["risk_threshold"] is not None else 0.5
    )
    assessment = _combine_checkin_assessment(
        geo_assessment, biometrics, effective_threshold
    )

    liveness = biometrics["liveness"]
    face_match = biometrics["face_match"]

    checkin_id = str(uuid.uuid4())
    checkin_status = assessment["status"]
    checkin_risk_factors = assessment["risk_factors"]

    new_checkin = CheckIn(
        id=checkin_id,
        session_id=checkin_data.session_id,
        student_id=current_user.id,
        status=checkin_status,
        checked_in_at=now,
        verified_at=now if checkin_status == "approved" else None,
        latitude=checkin_data.latitude,
        longitude=checkin_data.longitude,
        location_accuracy_meters=checkin_data.location_accuracy_meters,
        distance_from_venue_meters=geo_assessment["distance_from_venue_meters"],
        liveness_passed=liveness.passed if liveness else None,
        liveness_score=liveness.score if liveness else None,
        liveness_challenge_type=liveness.challenge_type if liveness else None,
        face_match_passed=face_match.passed if face_match else None,
        face_match_score=face_match.score if face_match else None,
        face_embedding_hash=biometrics["face_embedding_hash"],
        risk_score=assessment["risk_score"],
        risk_factors=(
            json.dumps(checkin_risk_factors) if checkin_risk_factors else None
        )
    )

    # Commit expires ORM instances, including the authenticated user.
    student_id = current_user.id
    db.add(new_checkin)
    db.commit()

    # Every field below was already known in Python before the insert (no
    # server-side defaults or triggers on this table), so the response is
    # built from those local values instead of re-reading new_checkin's
    # attributes post-commit. The session's default expire-on-commit
    # behaviour would otherwise make that first post-commit attribute
    # access trigger an implicit reload identical in cost to the
    # db.refresh() this replaces - so building from locals is what actually
    # avoids the round trip, not merely deleting the refresh call.
    return {
        "id": checkin_id,
        "session_id": checkin_data.session_id,
        "student_id": student_id,
        "status": checkin_status,
        "checked_in_at": now,
        "latitude": checkin_data.latitude,
        "longitude": checkin_data.longitude,
        "distance_from_venue_meters": geo_assessment["distance_from_venue_meters"],
        "liveness_passed": liveness.passed if liveness else None,
        "liveness_score": liveness.score if liveness else None,
        "liveness_challenge_type": liveness.challenge_type if liveness else None,
        "face_match_passed": face_match.passed if face_match else None,
        "face_match_score": face_match.score if face_match else None,
        "risk_score": assessment["risk_score"],
        "risk_factors": checkin_risk_factors if checkin_risk_factors else []
    }


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
    current_user: User = Depends(require_roles("instructor", "ta", "admin", read_only=True)),
    db: Session = Depends(get_read_db)
):
    # Single round trip: session existence, its check-ins, and each
    # check-in's student are all resolved via one LEFT JOIN chain rooted at
    # sessions. A nonexistent session yields zero rows (404 below); an
    # existing session with zero check-ins yields exactly one row with
    # CheckIn/User both None (falls through to an empty list, same as
    # before).
    rows = (
        db.query(SessionModel.id, CheckIn, User)
        .outerjoin(CheckIn, CheckIn.session_id == SessionModel.id)
        .outerjoin(User, User.id == CheckIn.student_id)
        .filter(SessionModel.id == session_id)
        .all()
    )

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    results = []

    for _, checkin, student in rows:
        if checkin is None or student is None:
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


def _serialize_device(device: Device) -> dict:
    return {
        "id": device.id,
        "user_id": device.user_id,
        "device_fingerprint": device.device_fingerprint,
        "device_name": device.device_name,
        "platform": device.platform,
        "browser": device.browser,
        "is_trusted": device.is_trusted,
        "trust_score": device.trust_score,
        "is_active": device.is_active,
        "first_seen_at": device.first_seen_at,
        "last_seen_at": device.last_seen_at,
        "total_checkins": device.total_checkins
    }


@app.post("/api/v1/devices/", status_code=status.HTTP_201_CREATED)
@app.post("/api/v1/devices/register", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def register_device(
    device_data: DeviceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    existing = db.query(Device).filter(
        Device.device_fingerprint == device_data.device_fingerprint
    ).first()

    if existing:
        if existing.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Device fingerprint already registered to another user"
            )

        # Re-registration from the device's owner (e.g. re-login on the same
        # browser) - refresh metadata and reactivate instead of erroring.
        existing.device_name = device_data.device_name or existing.device_name
        existing.platform = device_data.platform or existing.platform
        existing.browser = device_data.browser or existing.browser
        existing.os_version = device_data.os_version or existing.os_version
        existing.app_version = device_data.app_version or existing.app_version
        existing.public_key = device_data.public_key or existing.public_key
        existing.is_active = True
        existing.last_seen_at = datetime.utcnow()

        db.commit()
        db.refresh(existing)

        return _serialize_device(existing)

    now = datetime.utcnow()
    new_device = Device(
        user_id=current_user.id,
        device_fingerprint=device_data.device_fingerprint,
        device_name=device_data.device_name,
        platform=device_data.platform,
        browser=device_data.browser,
        os_version=device_data.os_version,
        app_version=device_data.app_version,
        public_key=device_data.public_key,
        first_seen_at=now,
        last_seen_at=now
    )

    db.add(new_device)
    db.commit()
    db.refresh(new_device)

    return _serialize_device(new_device)


@app.get("/api/v1/devices/my-devices")
def list_my_devices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    devices = db.query(Device).filter(
        Device.user_id == current_user.id
    ).all()

    return [_serialize_device(device) for device in devices]


@app.patch("/api/v1/devices/{device_id}")
def update_device(
    device_id: str,
    device_data: DeviceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    device = db.query(Device).filter(Device.id == device_id).first()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )

    if device.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )

    if device_data.is_trusted is not None:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can change device trust status"
            )
        device.is_trusted = device_data.is_trusted
        device.trust_score = "high" if device_data.is_trusted else "low"

    if device_data.device_name is not None:
        device.device_name = device_data.device_name

    if device_data.is_active is not None:
        device.is_active = device_data.is_active

    db.commit()
    db.refresh(device)

    return _serialize_device(device)


@app.delete("/api/v1/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    device = db.query(Device).filter(Device.id == device_id).first()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )

    if device.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )

    db.delete(device)
    db.commit()

    return None


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
