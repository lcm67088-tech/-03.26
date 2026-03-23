"""
인증 관련 Pydantic 스키마 (Sprint 2 완성)
Pydantic v2 field_validator 사용
"""
import re
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


# ============================
# 유효성 검증 헬퍼
# ============================

def _validate_password_strength(v: str) -> str:
    """
    비밀번호 강도 검증
    - 최소 8자
    - 영문 대문자 1개 이상
    - 영문 소문자 1개 이상
    - 숫자 1개 이상
    """
    if len(v) < 8:
        raise ValueError("비밀번호는 8자 이상이어야 합니다")
    if not re.search(r"[A-Z]", v):
        raise ValueError("비밀번호에 대문자를 포함해야 합니다")
    if not re.search(r"[a-z]", v):
        raise ValueError("비밀번호에 소문자를 포함해야 합니다")
    if not re.search(r"\d", v):
        raise ValueError("비밀번호에 숫자를 포함해야 합니다")
    return v


# ============================
# 요청 스키마
# ============================

class RegisterRequest(BaseModel):
    """회원가입 요청"""
    email: EmailStr
    password: str
    name: str
    phone: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_strength(v)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("이름은 2자 이상이어야 합니다")
        if len(v) > 50:
            raise ValueError("이름은 50자 이하여야 합니다")
        return v


class LoginRequest(BaseModel):
    """로그인 요청"""
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """토큰 갱신 요청"""
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    """비밀번호 찾기 요청"""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """비밀번호 재설정 요청"""
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return _validate_password_strength(v)


# ============================
# 응답 스키마
# ============================

class WorkspaceInfo(BaseModel):
    """워크스페이스 간략 정보 (토큰 응답 포함용)"""
    id: str
    name: str
    plan: str

    model_config = {"from_attributes": True}


class UserInfo(BaseModel):
    """유저 간략 정보 (토큰 응답 포함용)"""
    id: str
    email: str
    name: str
    role: str
    phone: Optional[str] = None
    is_active: bool
    email_verified: bool

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """로그인/토큰갱신 응답"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserInfo
    workspace: WorkspaceInfo


class RegisterResponse(BaseModel):
    """회원가입 응답"""
    user: UserInfo
    workspace: WorkspaceInfo
    message: str


class MeResponse(BaseModel):
    """현재 유저 정보 응답 (/me 엔드포인트)"""
    id: str
    email: str
    name: str
    role: str
    phone: Optional[str] = None
    is_active: bool
    email_verified: bool
    workspace: Optional[WorkspaceInfo] = None

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    """단순 메시지 응답"""
    message: str
    success: bool = True
