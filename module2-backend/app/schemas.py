from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from typing import Literal, Optional
from datetime import datetime


class RequestModel(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


class PasswordRequest(RequestModel):
    password: str = Field(max_length=72)

    @field_validator('password')
    @classmethod
    def bounded_password_bytes(cls, value):
        if len(value.encode('utf-8')) > 72:
            raise ValueError('Password must not exceed 72 UTF-8 bytes')
        return value


class UserRegister(PasswordRequest):
    email: EmailStr
    full_name: str
    password: str = Field(min_length=8, max_length=72)
    role: Literal["student", "ta", "instructor", "admin"] = "student"
class UserLogin(PasswordRequest):
    email: EmailStr
class RefreshTokenRequest(RequestModel):
    refresh_token: str
class UserUpdate(RequestModel):
    full_name: Optional[str] = None
    camera_consent: Optional[bool] = None
    geolocation_consent: Optional[bool] = None
class AdminUserUpdate(RequestModel):
    # docs/API-SPECIFICATION.md "PATCH /users/{user_id}" request fields.
    role: Optional[Literal["student", "ta", "instructor", "admin"]] = None
    is_active: Optional[bool] = None
class BulkUserCreate(RequestModel):
    # Items are validated one by one so a bad entry is reported in
    # ``errors`` instead of failing the whole batch.
    users: list[dict] = Field(min_length=1)
class CourseCreate(RequestModel):
    code: str
    name: str
    semester: str
    instructor_id: Optional[str] = None
    venue_name: Optional[str] = None
    venue_latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    venue_longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    geofence_radius_meters: float = Field(default=100.0, ge=0)
    require_face_recognition: bool = False
    require_device_binding: bool = True
    risk_threshold: float = Field(default=0.5, ge=0, le=1)
class CourseUpdate(RequestModel):
    name: Optional[str] = None
    semester: Optional[str] = None
    instructor_id: Optional[str] = None
    venue_name: Optional[str] = None
    venue_latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    venue_longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    geofence_radius_meters: Optional[float] = Field(default=None, ge=0)
    require_face_recognition: Optional[bool] = None
    require_device_binding: Optional[bool] = None
    risk_threshold: Optional[float] = Field(default=None, ge=0, le=1)
class EnrollmentCreate(RequestModel):
    course_id: str
    student_id: Optional[str] = None
    student_email: Optional[EmailStr] = None

    @model_validator(mode="after")
    def require_one_student_identifier(self):
        if (self.student_id is None) == (self.student_email is None):
            raise ValueError("Provide exactly one of student_id or student_email")
        return self
class TAAssignmentCreate(RequestModel):
    user_id: Optional[str] = None
    email: Optional[EmailStr] = None

    @model_validator(mode="after")
    def require_one_ta_identifier(self):
        if (self.user_id is None) == (self.email is None):
            raise ValueError("Provide exactly one of user_id or email")
        return self
class BulkEnrollmentCreate(RequestModel):
    course_id: str
    student_emails: list[EmailStr] = Field(min_length=1)
    create_accounts: bool = False
class SessionCreate(RequestModel):
    course_id: str
    name: str
    session_type: str = "lecture"
    description: Optional[str] = None
    scheduled_start: datetime
    scheduled_end: datetime
    checkin_opens_at: Optional[datetime] = None
    checkin_closes_at: Optional[datetime] = None
    venue_latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    venue_longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    venue_name: Optional[str] = None
    geofence_radius_meters: Optional[float] = Field(default=None, ge=0)
    require_motion_check: bool = False
    require_liveness_check: bool = True
    require_face_match: bool = False
    risk_threshold: Optional[float] = Field(default=None, ge=0, le=1)
class SessionUpdate(RequestModel):
    course_id: Optional[str] = None
    name: Optional[str] = None
    session_type: Optional[str] = None
    description: Optional[str] = None
    status: Optional[Literal["scheduled", "active", "closed", "cancelled"]] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    checkin_opens_at: Optional[datetime] = None
    checkin_closes_at: Optional[datetime] = None
    venue_latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    venue_longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    venue_name: Optional[str] = None
    geofence_radius_meters: Optional[float] = Field(default=None, ge=0)
    require_motion_check: Optional[bool] = None
    require_liveness_check: Optional[bool] = None
    require_face_match: Optional[bool] = None
    risk_threshold: Optional[float] = Field(default=None, ge=0, le=1)
class SessionStatusUpdate(RequestModel):
    status: Literal["scheduled", "active", "closed", "cancelled"]
class CheckInCreate(RequestModel):
    session_id: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    location_accuracy_meters: Optional[float] = Field(default=None, ge=0)
    device_fingerprint: str
    motion_verification_id: Optional[str] = Field(default=None, max_length=36)
    liveness_challenge_response: Optional[str] = None
    qr_code: Optional[str] = None
class CheckInAppeal(RequestModel):
    appeal_reason: str = Field(min_length=1)
class CheckInReview(RequestModel):
    status: Literal["approved", "rejected"]
    review_notes: Optional[str] = None
class FaceEnrollRequest(RequestModel):
    # Base64-encoded face image (PNG/JPEG), no data URL prefix. See
    # docs/API-SPECIFICATION.md "POST /users/me/face/enroll".
    image: str = Field(min_length=1)
class DeviceCreate(RequestModel):
    device_fingerprint: str = Field(min_length=1, max_length=64)
    device_name: Optional[str] = None
    platform: Optional[Literal["ios", "android", "web", "desktop"]] = None
    browser: Optional[str] = None
    os_version: Optional[str] = None
    app_version: Optional[str] = None
    public_key: Optional[str] = None
class DeviceUpdate(RequestModel):
    device_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    is_trusted: Optional[bool] = None
    is_active: Optional[bool] = None
