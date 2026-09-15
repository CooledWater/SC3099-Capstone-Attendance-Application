import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Enum,
    Index,
    Float,
    Integer,
    Text,
    ForeignKey,
)

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )

    full_name = Column(
        String(255),
        nullable=False
    )

    hashed_password = Column(
        String(255),
        nullable=False
    )

    role = Column(
        Enum(
            "student",
            "instructor",
            "ta",
            "admin",
            name="user_role"
        ),
        nullable=False
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True
    )

    camera_consent = Column(
        Boolean,
        default=False
    )

    geolocation_consent = Column(
        Boolean,
        default=False
    )

    face_embedding_hash = Column(
        String(64),
        nullable=True
    )

    face_enrolled = Column(
        Boolean,
        default=False
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    last_login_at = Column(
        DateTime,
        nullable=True
    )

    scheduled_deletion_at = Column(
        DateTime,
        nullable=True
    )


Index("ix_users_role", User.role)
Index("ix_users_is_active", User.is_active)


class Course(Base):
    __tablename__ = "courses"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    code = Column(
        String(20),
        unique=True,
        nullable=False,
        index=True
    )

    name = Column(
        String(255),
        nullable=False
    )

    semester = Column(
        String(20),
        nullable=False,
        index=True
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True
    )

    # Not listed in DATABASE-SCHEMA.md's courses table, but required by
    # API-SPECIFICATION.md's course response/permissions (instructor_id,
    # instructor_name, "admin or course instructor" on PUT /courses/{id}).
    instructor_id = Column(
        String(36),
        ForeignKey("users.id"),
        nullable=True
    )

    venue_latitude = Column(Float, nullable=True)
    venue_longitude = Column(Float, nullable=True)
    venue_name = Column(String(255), nullable=True)
    geofence_radius_meters = Column(Float, nullable=False, default=100.0)
    require_face_recognition = Column(Boolean, nullable=False, default=False)
    require_device_binding = Column(Boolean, nullable=False, default=True)
    risk_threshold = Column(Float, nullable=False, default=0.5)

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )


class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    student_id = Column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    course_id = Column(
        String(36),
        ForeignKey("courses.id"),
        nullable=False,
        index=True
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True
    )

    enrolled_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    dropped_at = Column(
        DateTime,
        nullable=True
    )


Index(
    "ix_enrollments_student_course",
    Enrollment.student_id,
    Enrollment.course_id,
    unique=True
)


class Session(Base):
    """A class meeting where students check in.

    Live DB introspection confirmed no `sessions` table exists yet (unlike
    `courses`, which already had a live table missing a documented column).
    This model is therefore authoritative for what create_all() will create,
    and follows DATABASE-SCHEMA.md's documented sessions table directly.
    """

    __tablename__ = "sessions"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    course_id = Column(
        String(36),
        ForeignKey("courses.id"),
        nullable=False,
        index=True
    )

    instructor_id = Column(
        String(36),
        ForeignKey("users.id"),
        nullable=True
    )

    name = Column(
        String(255),
        nullable=False
    )

    session_type = Column(
        String(50),
        nullable=False,
        default="lecture"
    )

    description = Column(
        Text,
        nullable=True
    )

    scheduled_start = Column(DateTime, nullable=False)
    scheduled_end = Column(DateTime, nullable=False)
    checkin_opens_at = Column(DateTime, nullable=False)
    checkin_closes_at = Column(DateTime, nullable=False)

    status = Column(
        Enum(
            "scheduled",
            "active",
            "closed",
            "cancelled",
            name="session_status"
        ),
        nullable=False,
        default="scheduled",
        index=True
    )

    actual_start = Column(DateTime, nullable=True)
    actual_end = Column(DateTime, nullable=True)

    venue_latitude = Column(Float, nullable=True)
    venue_longitude = Column(Float, nullable=True)
    venue_name = Column(String(255), nullable=True)
    geofence_radius_meters = Column(Float, nullable=True)

    require_liveness_check = Column(Boolean, nullable=False, default=True)
    require_face_match = Column(Boolean, nullable=False, default=False)
    risk_threshold = Column(Float, nullable=True)

    # Not used yet (QR check-in is out of scope this round); columns kept
    # nullable so the table matches DATABASE-SCHEMA.md's documented schema.
    qr_code_secret = Column(String(64), nullable=True)
    qr_code_expires_at = Column(DateTime, nullable=True)

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )


Index("ix_sessions_scheduled_start", Session.scheduled_start)
Index(
    "ix_sessions_checkin_window",
    Session.checkin_opens_at,
    Session.checkin_closes_at
)


class CheckIn(Base):
    """A student's attendance record for a session.

    Live DB introspection confirmed no `checkins` table exists yet, so this
    follows DATABASE-SCHEMA.md's documented columns directly (same situation
    as `sessions` last time). Fields belonging to later weeks (liveness,
    face match, review/appeal, risk factors) are included as nullable
    columns only so the table won't need a migration when those features
    land - none of that logic is implemented by this model or its endpoints.
    """

    __tablename__ = "checkins"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    session_id = Column(
        String(36),
        ForeignKey("sessions.id"),
        nullable=False,
        index=True
    )

    student_id = Column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    # devices table does not exist yet (Week 4 device management is out of
    # scope this round), so this is intentionally NOT a ForeignKey - adding
    # one would fail table creation against a nonexistent target table.
    device_id = Column(String(36), nullable=True)

    status = Column(
        Enum(
            "pending",
            "approved",
            "flagged",
            "rejected",
            "appealed",
            name="checkin_status"
        ),
        nullable=False,
        default="pending",
        index=True
    )

    checked_in_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True
    )

    verified_at = Column(DateTime, nullable=True)

    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    location_accuracy_meters = Column(Float, nullable=True)
    distance_from_venue_meters = Column(Float, nullable=True)

    liveness_passed = Column(Boolean, nullable=True)
    liveness_score = Column(Float, nullable=True)
    liveness_challenge_type = Column(String(50), nullable=True)

    face_match_passed = Column(Boolean, nullable=True)
    face_match_score = Column(Float, nullable=True)
    face_embedding_hash = Column(String(64), nullable=True)

    risk_score = Column(Float, nullable=False, default=0.0, index=True)
    risk_factors = Column(Text, nullable=True)

    qr_code_verified = Column(Boolean, nullable=False, default=False)

    reviewed_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)

    appeal_reason = Column(Text, nullable=True)
    appealed_at = Column(DateTime, nullable=True)

    scheduled_deletion_at = Column(DateTime, nullable=True)


Index(
    "ix_checkins_session_student",
    CheckIn.session_id,
    CheckIn.student_id,
    unique=True
)


class Device(Base):
    """A user's registered device, per DATABASE-SCHEMA.md's devices table.

    ``public_key`` is documented as NOT NULL there (device-binding attestation
    is a later feature), but no current client sends one, so it's kept
    nullable here - registration must not fail for callers that only send
    fingerprint/name/platform/browser.
    """

    __tablename__ = "devices"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    user_id = Column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    device_fingerprint = Column(
        String(64),
        unique=True,
        nullable=False,
        index=True
    )

    device_name = Column(String(255), nullable=True)
    platform = Column(String(50), nullable=True)
    browser = Column(String(100), nullable=True)
    os_version = Column(String(50), nullable=True)
    app_version = Column(String(50), nullable=True)

    public_key = Column(Text, nullable=True)
    public_key_created_at = Column(DateTime, nullable=True)
    public_key_expires_at = Column(DateTime, nullable=True)

    attestation_passed = Column(Boolean, nullable=False, default=False)
    last_attestation_at = Column(DateTime, nullable=True)

    is_trusted = Column(Boolean, nullable=False, default=False, index=True)
    trust_score = Column(String(20), nullable=False, default="low")
    is_emulator = Column(Boolean, nullable=False, default=False)
    is_rooted_jailbroken = Column(Boolean, nullable=False, default=False)

    first_seen_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    last_seen_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    total_checkins = Column(Integer, nullable=False, default=0)

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True
    )

    revoked_at = Column(DateTime, nullable=True)
    revocation_reason = Column(Text, nullable=True)