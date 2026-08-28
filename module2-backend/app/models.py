import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Enum,
    Index,
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