import uuid
from datetime import datetime

from app.models.domain import UserRole
from pydantic import BaseModel, EmailStr, Field

# --- Request schemas ---


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    role: UserRole = UserRole.customer


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# --- Response schemas ---


class RegisterResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: UserRole


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ValidateResponse(BaseModel):
    user_id: str
    role: UserRole


class MessageResponse(BaseModel):
    message: str
