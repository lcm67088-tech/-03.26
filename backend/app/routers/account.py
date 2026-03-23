"""
계정 라우터 모듈
Sprint 7: 계정 프로필/비밀번호/워크스페이스 관리 엔드포인트 (5개)

엔드포인트 목록:
  GET  /api/v1/account/profile     - 프로필 조회
  PUT  /api/v1/account/profile     - 프로필 수정
  PUT  /api/v1/account/password    - 비밀번호 변경
  GET  /api/v1/account/workspaces  - 소속 워크스페이스 목록
  POST /api/v1/account/workspaces  - 새 워크스페이스 생성 (최대 5개)
"""

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.models.workspace import MemberRole, Workspace, WorkspaceMember, WorkspacePlan

router = APIRouter(prefix="/account", tags=["account"])


# ─────────────────────────────────────────────────────────────
# 로컬 스키마 (account 전용)
# ─────────────────────────────────────────────────────────────

class ProfileResponse(BaseModel):
    """계정 프로필 응답 스키마"""
    id: uuid.UUID
    email: str
    name: str
    phone: Optional[str] = None
    profile_image_url: Optional[str] = None
    role: str
    created_at: datetime
    current_workspace_id: Optional[uuid.UUID] = None

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    """프로필 수정 요청 스키마 (이메일 수정 불가)"""
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="이름")
    phone: Optional[str] = Field(None, max_length=20, description="전화번호")
    profile_image_url: Optional[str] = Field(None, max_length=500, description="프로필 이미지 URL")


class PasswordChange(BaseModel):
    """비밀번호 변경 요청 스키마"""
    current_password: str = Field(..., description="현재 비밀번호")
    new_password: str = Field(..., min_length=8, description="새 비밀번호 (최소 8자)")
    confirm_password: str = Field(..., description="새 비밀번호 확인")


class WorkspaceListItem(BaseModel):
    """워크스페이스 목록 항목 스키마"""
    id: uuid.UUID
    name: str
    plan: str
    role: str
    member_count: int
    place_count: int

    model_config = {"from_attributes": True}


class WorkspaceCreate(BaseModel):
    """워크스페이스 생성 요청 스키마"""
    name: str = Field(..., min_length=1, max_length=100, description="워크스페이스 이름")


# ─────────────────────────────────────────────────────────────
# GET /account/profile - 프로필 조회
# ─────────────────────────────────────────────────────────────

@router.get("/profile", response_model=ProfileResponse)
def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    현재 로그인한 사용자의 프로필을 반환합니다.
    current_workspace_id: 사용자가 소속된 첫 번째 워크스페이스 ID
    """
    # 첫 번째 워크스페이스 ID 조회
    membership = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.user_id == current_user.id)
        .order_by(WorkspaceMember.created_at)
        .first()
    )
    current_workspace_id = membership.workspace_id if membership else None

    return ProfileResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        phone=getattr(current_user, "phone", None),
        profile_image_url=getattr(current_user, "profile_image_url", None),
        role=current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
        created_at=current_user.created_at,
        current_workspace_id=current_workspace_id,
    )


# ─────────────────────────────────────────────────────────────
# PUT /account/profile - 프로필 수정
# ─────────────────────────────────────────────────────────────

@router.put("/profile", response_model=ProfileResponse)
def update_profile(
    body: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    현재 사용자의 프로필을 수정합니다.
    이메일은 수정 불가. name/phone/profile_image_url만 수정 가능.
    """
    # 수정할 필드가 있는 경우에만 업데이트
    if body.name is not None:
        current_user.name = body.name
    if body.phone is not None:
        current_user.phone = body.phone
    if body.profile_image_url is not None:
        current_user.profile_image_url = body.profile_image_url

    db.commit()
    db.refresh(current_user)

    # 첫 번째 워크스페이스 ID 조회
    membership = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.user_id == current_user.id)
        .order_by(WorkspaceMember.created_at)
        .first()
    )
    current_workspace_id = membership.workspace_id if membership else None

    return ProfileResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        phone=getattr(current_user, "phone", None),
        profile_image_url=getattr(current_user, "profile_image_url", None),
        role=current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
        created_at=current_user.created_at,
        current_workspace_id=current_workspace_id,
    )


# ─────────────────────────────────────────────────────────────
# PUT /account/password - 비밀번호 변경
# ─────────────────────────────────────────────────────────────

@router.put("/password")
def change_password(
    body: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    현재 사용자의 비밀번호를 변경합니다.
    - 현재 비밀번호 검증 후 진행
    - new_password == confirm_password 확인
    - bcrypt 해싱 후 저장
    """
    # 현재 비밀번호 검증
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=400,
            detail="현재 비밀번호가 올바르지 않습니다.",
        )

    # 새 비밀번호 일치 확인
    if body.new_password != body.confirm_password:
        raise HTTPException(
            status_code=400,
            detail="새 비밀번호와 확인 비밀번호가 일치하지 않습니다.",
        )

    # 현재 비밀번호와 동일한 경우 방지
    if verify_password(body.new_password, current_user.hashed_password):
        raise HTTPException(
            status_code=400,
            detail="새 비밀번호는 현재 비밀번호와 달라야 합니다.",
        )

    # bcrypt 해싱 후 저장
    current_user.hashed_password = get_password_hash(body.new_password)
    db.commit()

    return {"message": "비밀번호가 성공적으로 변경되었습니다."}


# ─────────────────────────────────────────────────────────────
# GET /account/workspaces - 소속 워크스페이스 목록
# ─────────────────────────────────────────────────────────────

@router.get("/workspaces", response_model=List[WorkspaceListItem])
def get_my_workspaces(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    현재 사용자가 멤버로 속한 모든 워크스페이스 목록을 반환합니다.
    각 항목에 role, member_count, place_count 포함.
    """
    # 현재 사용자의 멤버십 조회
    memberships = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.user_id == current_user.id)
        .all()
    )

    result = []
    for membership in memberships:
        workspace = membership.workspace
        if workspace is None or getattr(workspace, "is_deleted", False):
            continue

        # 멤버 수
        member_count = (
            db.query(WorkspaceMember)
            .filter(WorkspaceMember.workspace_id == workspace.id)
            .count()
        )

        # 플레이스 수
        from app.models.place import Place
        place_count = (
            db.query(Place)
            .filter(
                Place.workspace_id == workspace.id,
                Place.is_deleted == False,
            )
            .count()
        )

        result.append(
            WorkspaceListItem(
                id=workspace.id,
                name=workspace.name,
                plan=workspace.plan.value if hasattr(workspace.plan, "value") else str(workspace.plan),
                role=membership.role.value if hasattr(membership.role, "value") else str(membership.role),
                member_count=member_count,
                place_count=place_count,
            )
        )

    return result


# ─────────────────────────────────────────────────────────────
# POST /account/workspaces - 새 워크스페이스 생성
# ─────────────────────────────────────────────────────────────

@router.post("/workspaces", response_model=WorkspaceListItem, status_code=201)
def create_workspace(
    body: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    새 워크스페이스를 생성합니다.
    - 최대 5개 초과 시 403 에러 반환
    - 생성 시 현재 사용자를 owner로 WorkspaceMember 자동 생성
    """
    # 현재 사용자의 워크스페이스 수 확인
    current_count = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.user_id == current_user.id)
        .count()
    )

    if current_count >= 5:
        raise HTTPException(
            status_code=403,
            detail="워크스페이스는 최대 5개까지 생성할 수 있습니다.",
        )

    now = datetime.utcnow()

    # 워크스페이스 생성 (기본 플랜: free)
    workspace = Workspace(
        name=body.name,
        plan=WorkspacePlan.free,
        created_at=now,
        updated_at=now,
    )
    db.add(workspace)
    db.flush()  # workspace.id 생성

    # 현재 사용자를 owner로 멤버 등록
    membership = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=current_user.id,
        role=MemberRole.owner,
        created_at=now,
    )
    db.add(membership)
    db.commit()
    db.refresh(workspace)

    return WorkspaceListItem(
        id=workspace.id,
        name=workspace.name,
        plan=workspace.plan.value if hasattr(workspace.plan, "value") else str(workspace.plan),
        role=MemberRole.owner.value,
        member_count=1,
        place_count=0,
    )
