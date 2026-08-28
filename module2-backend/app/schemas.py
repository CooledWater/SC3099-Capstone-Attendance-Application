from pydantic import BaseModel, EmailStr
from typing import Literal


class UserRegister(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: Literal["student", "ta", "instructor", "admin"]
class UserLogin(BaseModel):
    email: EmailStr
    password: str
class RefreshTokenRequest(BaseModel):
    refresh_token: str