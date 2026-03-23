"""
워크스페이스 라우터 (Sprint 3 완성)

GET /api/v1/workspaces/me        현재 유저의 워크스페이스 목록
GET /api/v1/workspaces/{id}      워크스페이스 상세 + 플랜 한도
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.constants import get_plan_limits
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.keyword import PlaceKeyword
from app.models.place import Place
from app.models.user import User
from app.models.workspace import MemberRole, Workspace, WorkspaceMember

router = APIRouter()


# ============================
# 응답 스키마 (로컬 정의 — workspace 전용)
# ============================

class WorkspaceListItem(BaseModel):
    """워크스페이스 목록 아이템"""
    id: str
    name: str
    plan: str
    role: str                   # 현재 유저의 멤버 역할
    place_count: int
    keyword_count: int
    member_count: int

    model_config = {"from_attributes": True}


class PlanLimitsInfo(BaseModel):
    """플랜 한도 정보"""
    max_places: int
    max_keywords: int
    crawl_per_day: int


class WorkspaceDetail(BaseModel):
    """워크스페이스 상세 응답"""
    id: str
    name: str
    plan: str
    role: str                   # 현재 유저의 멤버 역할
    limits: PlanLimitsInfo
    place_count: int
    keyword_count: int
    member_count: int

    model_config = {"from_attributes": True}


# ============================
# 헬퍼 함수
# ============================

def _get_place_count(workspace_id: Any, db: Session) -> int:
    """워크스페이스의 활성 장소 수 조회"""
    return db.query(func.count(Place.id)).filter(
        Place.workspace_id == workspace_id,
        Place.is_active == True,
    ).scalar() or 0


def _get_keyword_count(workspace_id: Any, db: Session) -> int:
    """워크스페이스의 활성 키워드 수 조회"""
    return (
        db.query(func.count(PlaceKeyword.id))
        .join(Place, Place.id == PlaceKeyword.place_id)
        .filter(
            Place.workspace_id == workspace_id,
            Place.is_active == True,
            PlaceKeyword.is_active == True,
        )
        .scalar() or 0
    )


def _get_member_count(workspace_id: Any, db: Session) -> int:
    """워크스페이스 멤버 수 조회"""
    return db.query(func.count(WorkspaceMember.id)).filter(
        WorkspaceMember.workspace_id == workspace_id,
    ).scalar() or 0


# ============================
# 엔드포인트
# ============================

@router.get("/me", response_model=list[WorkspaceListItem])
async def get_my_workspaces(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    현재 유저가 속한 워크스페이스 목록 반환.

    WorkspaceMember 조인으로 현재 유저의 role 포함.
    각 워크스페이스의 장소 수, 키워드 수, 멤버 수 포함.
    """
    # 현재 유저의 멤버십 + 워크스페이스 조인 조회
    memberships = (
        db.query(WorkspaceMember, Workspace)
        .join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
        .filter(
            WorkspaceMember.user_id == current_user.id,
            Workspace.is_active == True,
        )
        .all()
    )

    result: list[WorkspaceListItem] = []
    for member, workspace in memberships:
        result.append(
            WorkspaceListItem(
                id=str(workspace.id),
                name=workspace.name,
                plan=workspace.plan.value,
                role=member.role.value,
                place_count=_get_place_count(workspace.id, db),
                keyword_count=_get_keyword_count(workspace.id, db),
                member_count=_get_member_count(workspace.id, db),
            )
        )

    return result


@router.get("/{workspace_id}", response_model=WorkspaceDetail)
async def get_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    워크스페이스 상세 조회.

    - 현재 유저가 해당 워크스페이스 멤버인지 검증
    - 플랜별 사용 한도 포함
    """
    # 워크스페이스 존재 여부 체크
    workspace = db.query(Workspace).filter(
        Workspace.id == workspace_id,
        Workspace.is_active == True,
    ).first()

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다",
        )

    # 멤버십 검증 (어드민은 무조건 통과)
    from app.models.user import UserRole
    if current_user.role in (UserRole.ADMIN, UserRole.SUPERADMIN):
        role_value = MemberRole.OWNER.value
    else:
        member = db.query(WorkspaceMember).filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == current_user.id,
        ).first()

        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="해당 워크스페이스에 접근 권한이 없습니다",
            )
        role_value = member.role.value

    # 플랜 한도 조회
    limits = get_plan_limits(workspace.plan.value)

    return WorkspaceDetail(
        id=str(workspace.id),
        name=workspace.name,
        plan=workspace.plan.value,
        role=role_value,
        limits=PlanLimitsInfo(**limits),
        place_count=_get_place_count(workspace.id, db),
        keyword_count=_get_keyword_count(workspace.id, db),
        member_count=_get_member_count(workspace.id, db),
    )
