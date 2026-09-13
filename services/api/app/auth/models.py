"""
TRACE — Auth Pydantic Models
Request/response schemas for authentication and user management.
"""

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    admin = "admin"
    investigator = "investigator"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserOut"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: UserRole = UserRole.investigator


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class PasswordReset(BaseModel):
    new_password: str


class CaseCreate(BaseModel):
    name: str
    description: str = ""


class CaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    culprit_entity_ids: Optional[list[str]] = None
    charges: Optional[list[str]] = None
    closure_notes: Optional[str] = None


class CaseOut(BaseModel):
    id: str
    name: str
    description: str
    created_by: str
    created_at: datetime
    status: str
    culprit_entity_ids: list[str] = []
    charges: list[str] = []
    closure_notes: str = ""
    closed_at: Optional[datetime] = None
    closed_by: Optional[str] = None


class CaseAssignment(BaseModel):
    user_id: str
