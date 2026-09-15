from pydantic import BaseModel, EmailStr, Field
from typing import Literal, Optional
from datetime import datetime


class UserRegister(BaseModel):
    email: EmailStr
    full_name: str
    password: str = Field(min_length=8)
    role: Literal["student", "ta", "instructor", "admin"] = "student"
class UserLogin(BaseModel):
    email: EmailStr
    password: str
class RefreshTokenRequest(BaseModel):
    refresh_token: str
class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    camera_consent: Optional[bool] = None
    geolocation_consent: Optional[bool] = None
class CourseCreate(BaseModel):
    code: str
    name: str
    semester: str
    instructor_id: Optional[str] = None
    venue_name: Optional[str] = None
    venue_latitude: Optional[float] = None
    venue_longitude: Optional[float] = None
    geofence_radius_meters: float = 100.0
    require_face_recognition: bool = False
    require_device_binding: bool = True
    risk_threshold: float = 0.5
class CourseUpdate(BaseModel):
    name: Optional[str] = None
    semester: Optional[str] = None
    instructor_id: Optional[str] = None
    venue_name: Optional[str] = None
    venue_latitude: Optional[float] = None
    venue_longitude: Optional[float] = None
    geofence_radius_meters: Optional[float] = None
    require_face_recognition: Optional[bool] = None
    require_device_binding: Optional[bool] = None
    risk_threshold: Optional[float] = None
class EnrollmentCreate(BaseModel):
    student_id: str
    course_id: str
class SessionCreate(BaseModel):
    course_id: str
    name: str
    session_type: str = "lecture"
    description: Optional[str] = None
    scheduled_start: datetime
    scheduled_end: datetime
    checkin_opens_at: Optional[datetime] = None
    checkin_closes_at: Optional[datetime] = None
    venue_latitude: Optional[float] = None
    venue_longitude: Optional[float] = None
    venue_name: Optional[str] = None
    geofence_radius_meters: Optional[float] = None
    require_liveness_check: bool = True
    require_face_match: bool = False
    risk_threshold: Optional[float] = None
class SessionUpdate(BaseModel):
    name: Optional[str] = None
    session_type: Optional[str] = None
    description: Optional[str] = None
    status: Optional[Literal["scheduled", "active", "closed", "cancelled"]] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    checkin_opens_at: Optional[datetime] = None
    checkin_closes_at: Optional[datetime] = None
    venue_latitude: Optional[float] = None
    venue_longitude: Optional[float] = None
    venue_name: Optional[str] = None
    geofence_radius_meters: Optional[float] = None
    require_liveness_check: Optional[bool] = None
    require_face_match: Optional[bool] = None
    risk_threshold: Optional[float] = None
class SessionStatusUpdate(BaseModel):
    status: Literal["scheduled", "active", "closed", "cancelled"]
class CheckInCreate(BaseModel):
    session_id: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    location_accuracy_meters: Optional[float] = None
    device_fingerprint: str
    liveness_challenge_response: Optional[str] = None
    qr_code: Optional[str] = None
class FaceEnrollRequest(BaseModel):
    # Base64-encoded face image (PNG/JPEG), no data URL prefix. See
    # docs/API-SPECIFICATION.md "POST /users/me/face/enroll".
    image: str = Field(min_length=1)
class DeviceCreate(BaseModel):
    device_fingerprint: str = Field(min_length=1, max_length=64)
    device_name: Optional[str] = None
    platform: Optional[Literal["ios", "android", "web", "desktop"]] = None
    browser: Optional[str] = None
    os_version: Optional[str] = None
    app_version: Optional[str] = None
    public_key: Optional[str] = None
class DeviceUpdate(BaseModel):
    device_name: Optional[str] = None
    is_trusted: Optional[bool] = None
    is_active: Optional[bool] = None
