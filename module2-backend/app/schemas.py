from pydantic import BaseModel, EmailStr, Field
from typing import Literal, Optional


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
