"""
Workspace 스키마
"""
from datetime import datetime
from typing import Optional, Any, Dict
from uuid import UUID

from pydantic import BaseModel

from app.models.workspace import WorkspacePlan, MemberRole


class WorkspaceCreate(BaseModel):
    """워크스페이스 생성 요청"""
    name: str


class WorkspaceUpdate(BaseModel):
    """워크스페이스 수정"""
    name: Optional[str] = None


class WorkspaceResponse(BaseModel):
    """워크스페이스 응답"""
    id: UUID
    owner_id: UUID
    name: str
    plan: WorkspacePlan
    is_active: bool
    extra_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkspaceMemberResponse(BaseModel):
    """워크스페이스 멤버 응답"""
    id: UUID
    workspace_id: UUID
    user_id: UUID
    role: MemberRole
    created_at: datetime

    class Config:
        from_attributes = True


class InviteMemberRequest(BaseModel):
    """멤버 초대 요청"""
    email: str
    role: MemberRole = MemberRole.VIEWER
