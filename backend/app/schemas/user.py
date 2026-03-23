"""
User 스키마
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr

from app.models.user import UserRole


class UserCreate(BaseModel):
    """유저 생성 요청"""
    email: EmailStr
    password: str
    name: str
    phone: Optional[str] = None


class UserUpdate(BaseModel):
    """유저 정보 수정"""
    name: Optional[str] = None
    phone: Optional[str] = None


class UserResponse(BaseModel):
    """유저 응답"""
    id: UUID
    email: str
    name: str
    phone: Optional[str] = None
    role: UserRole
    is_active: bool
    email_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True
