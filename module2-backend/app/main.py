"""
SAIV Backend API - Module 2

This is the skeleton implementation for the Backend API module.
Students must implement all endpoints according to the API specification.

See: docs/API-SPECIFICATION.md for complete endpoint documentation.
"""

import html

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import engine, Base, get_db
from app import models
from app.models import User
from app.schemas import UserRegister, UserLogin, RefreshTokenRequest, UserUpdate
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
# Course Management Endpoints (courses.py)
# -----------------------------------------------------------------------------
# GET /courses - List courses
# GET /courses/{id} - Course details
# PATCH /courses/{id} - Update course

# -----------------------------------------------------------------------------
# Session Management Endpoints (sessions.py)
# -----------------------------------------------------------------------------
# POST /sessions - Create session (instructor)
# GET /sessions - List sessions
# GET /sessions/{id} - Session details
# PATCH /sessions/{id} - Update session
# DELETE /sessions/{id} - Delete session

# -----------------------------------------------------------------------------
# Check-in Endpoints (checkins.py)
# -----------------------------------------------------------------------------
# POST /checkins - Submit check-in
# GET /checkins - List check-ins (with filters)
# GET /checkins/me - Student's own check-ins
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
# PATCH /admin/sessions/{session_id}/status - Update session status (admin only)
# POST /admin/enrollments/ - Admin enrollment creation (admin only)

# =============================================================================
# Database Models to Implement (see DATABASE-SCHEMA.md)
# =============================================================================
# - users
# - courses
# - enrollments
# - sessions
# - checkins
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
