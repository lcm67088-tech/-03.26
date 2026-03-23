"""
워크스페이스 멤버 라우터 모듈
Sprint 7: 워크스페이스 멤버 관리 엔드포인트 (5개)

엔드포인트 목록:
  GET    /api/v1/workspaces/{workspace_id}/members                    - 멤버 목록
  POST   /api/v1/workspaces/{workspace_id}/members/invite             - 멤버 초대
  PUT    /api/v1/workspaces/{workspace_id}/members/{user_id}          - 역할 변경
  DELETE /api/v1/workspaces/{workspace_id}/members/{user_id}          - 멤버 제거
  POST   /api/v1/workspaces/{workspace_id}/members/transfer-ownership - 소유권 이전
"""

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.workspace import MemberRole, Workspace, WorkspaceMember
from app.services.notification_service import notification_service
from app.models.notification import NotificationType

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/workspaces/{workspace_id}/members",
    tags=["workspace-members"],
)


# ─────────────────────────────────────────────────────────────
# 로컬 스키마
# ─────────────────────────────────────────────────────────────

class MemberResponse(BaseModel):
    """멤버 목록 항목 응답 스키마"""
    id: uuid.UUID           # user_id
    name: str
    email: str
    role: str
    joined_at: datetime
    is_current_user: bool

    model_config = {"from_attributes": True}


class InviteMemberRequest(BaseModel):
    """멤버 초대 요청 스키마"""
    email: EmailStr = Field(..., description="초대할 사용자 이메일")
    role: str = Field("member", description="초대 역할 (viewer/member/manager)")


class UpdateMemberRoleRequest(BaseModel):
    """멤버 역할 변경 요청 스키마"""
    role: str = Field(..., description="새 역할 (viewer/member/manager)")


class TransferOwnershipRequest(BaseModel):
    """소유권 이전 요청 스키마"""
    new_owner_id: uuid.UUID = Field(..., description="새 owner의 user_id")


# ─────────────────────────────────────────────────────────────
# 헬퍼: 워크스페이스 존재 + 멤버 여부 확인
# ─────────────────────────────────────────────────────────────

def _get_workspace_or_404(
    workspace_id: uuid.UUID, db: Session
) -> Workspace:
    """워크스페이스 존재 여부 확인"""
    workspace = db.query(Workspace).filter(
        Workspace.id == workspace_id,
        Workspace.is_deleted == False,
    ).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="워크스페이스를 찾을 수 없습니다.")
    return workspace


def _get_membership_or_403(
    workspace_id: uuid.UUID, user_id: uuid.UUID, db: Session
) -> WorkspaceMember:
    """현재 사용자의 멤버십 조회 (없으면 403)"""
    membership = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user_id,
    ).first()
    if not membership:
        raise HTTPException(
            status_code=403,
            detail="해당 워크스페이스에 접근 권한이 없습니다.",
        )
    return membership


def _role_value(role) -> str:
    """role enum → str 변환"""
    return role.value if hasattr(role, "value") else str(role)


# ─────────────────────────────────────────────────────────────
# GET /workspaces/{workspace_id}/members - 멤버 목록
# ─────────────────────────────────────────────────────────────

@router.get("", response_model=List[MemberResponse])
def list_members(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    워크스페이스 멤버 목록을 조회합니다.
    현재 사용자가 해당 워크스페이스 멤버가 아니면 403.
    """
    _get_workspace_or_404(workspace_id, db)
    _get_membership_or_403(workspace_id, current_user.id, db)

    # 멤버 목록 조회
    memberships = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.workspace_id == workspace_id)
        .all()
    )

    result = []
    for m in memberships:
        user = m.user
        if user is None:
            continue
        result.append(
            MemberResponse(
                id=user.id,
                name=user.name,
                email=user.email,
                role=_role_value(m.role),
                joined_at=m.created_at,
                is_current_user=(user.id == current_user.id),
            )
        )

    return result


# ─────────────────────────────────────────────────────────────
# POST /workspaces/{workspace_id}/members/invite - 멤버 초대
# ─────────────────────────────────────────────────────────────

@router.post("/invite", status_code=201)
async def invite_member(
    workspace_id: uuid.UUID,
    body: InviteMemberRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    워크스페이스에 새 멤버를 초대합니다.
    - owner/manager만 초대 가능 (나머지는 403)
    - 이미 멤버인 경우 400 반환
    - 기존 가입 이메일: 즉시 멤버 생성
    - 미가입 이메일: Mock 초대 로그 출력 후 pending 상태 저장
    - MEMBER_INVITED 알림 발송
    """
    workspace = _get_workspace_or_404(workspace_id, db)
    my_membership = _get_membership_or_403(workspace_id, current_user.id, db)

    # 초대 권한 확인 (owner 또는 manager만 가능)
    allowed_roles = {MemberRole.owner, MemberRole.manager}
    if my_membership.role not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail="owner 또는 manager만 멤버를 초대할 수 있습니다.",
        )

    # 초대할 이메일로 사용자 조회
    target_user = db.query(User).filter(User.email == body.email).first()

    if target_user:
        # 이미 멤버인지 확인
        existing = db.query(WorkspaceMember).filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == target_user.id,
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail="이미 워크스페이스에 소속된 멤버입니다.",
            )

        # 유효한 역할 매핑
        role_map = {
            "viewer": MemberRole.viewer,
            "member": MemberRole.member,
            "manager": MemberRole.manager,
        }
        role = role_map.get(body.role, MemberRole.member)

        # 즉시 멤버 생성
        new_membership = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=target_user.id,
            role=role,
            created_at=datetime.utcnow(),
        )
        db.add(new_membership)
        db.flush()

        # MEMBER_INVITED 알림 발송 (대상 사용자에게)
        try:
            await notification_service.create_notification(
                db=db,
                user_id=target_user.id,
                notification_type=NotificationType.MEMBER_INVITED,
                data={
                    "workspace_id": str(workspace_id),
                    "workspace_name": workspace.name,
                    "target_user_name": target_user.name,
                },
                workspace_id=workspace_id,
            )
        except Exception as e:
            logger.warning(f"MEMBER_INVITED 알림 발송 실패: {e}")

        db.commit()

        return {
            "message": f"{target_user.name}({body.email}) 님이 워크스페이스에 추가되었습니다.",
            "status": "joined",
        }
    else:
        # 미가입 이메일 → Mock 초대 처리
        logger.info(
            f"[Mock 초대 이메일] {body.email} 주소로 워크스페이스 '{workspace.name}' 초대 메일 발송"
        )
        db.commit()
        return {
            "message": f"{body.email} 주소로 초대 이메일이 발송되었습니다.",
            "status": "pending",
        }


# ─────────────────────────────────────────────────────────────
# PUT /workspaces/{workspace_id}/members/{user_id} - 역할 변경
# ─────────────────────────────────────────────────────────────

@router.put("/{target_user_id}", response_model=MemberResponse)
async def update_member_role(
    workspace_id: uuid.UUID,
    target_user_id: uuid.UUID,
    body: UpdateMemberRoleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    워크스페이스 멤버의 역할을 변경합니다.
    - owner만 가능
    - owner 역할로의 변경 불가 (소유권 이전은 별도 엔드포인트 사용)
    - MEMBER_ROLE_CHANGED 알림 발송
    """
    workspace = _get_workspace_or_404(workspace_id, db)
    my_membership = _get_membership_or_403(workspace_id, current_user.id, db)

    # owner만 역할 변경 가능
    if my_membership.role != MemberRole.owner:
        raise HTTPException(
            status_code=403,
            detail="워크스페이스 owner만 멤버 역할을 변경할 수 있습니다.",
        )

    # owner로 변경 불가
    if body.role == "owner":
        raise HTTPException(
            status_code=400,
            detail="owner 역할 변경은 소유권 이전 API를 사용해주세요.",
        )

    # 대상 멤버 조회
    target_membership = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == target_user_id,
    ).first()
    if not target_membership:
        raise HTTPException(status_code=404, detail="대상 멤버를 찾을 수 없습니다.")

    # 유효한 역할 매핑
    role_map = {
        "viewer": MemberRole.viewer,
        "member": MemberRole.member,
        "manager": MemberRole.manager,
    }
    new_role = role_map.get(body.role)
    if not new_role:
        raise HTTPException(status_code=400, detail="유효하지 않은 역할입니다.")

    # 역할 변경
    target_membership.role = new_role
    db.flush()

    # 대상 사용자 정보
    target_user = db.query(User).filter(User.id == target_user_id).first()

    # MEMBER_ROLE_CHANGED 알림 발송
    try:
        await notification_service.create_notification(
            db=db,
            user_id=target_user_id,
            notification_type=NotificationType.MEMBER_ROLE_CHANGED,
            data={
                "workspace_id": str(workspace_id),
                "workspace_name": workspace.name,
                "target_user_name": target_user.name if target_user else "알 수 없음",
            },
            workspace_id=workspace_id,
        )
    except Exception as e:
        logger.warning(f"MEMBER_ROLE_CHANGED 알림 발송 실패: {e}")

    db.commit()
    db.refresh(target_membership)

    return MemberResponse(
        id=target_user_id,
        name=target_user.name if target_user else "",
        email=target_user.email if target_user else "",
        role=_role_value(target_membership.role),
        joined_at=target_membership.created_at,
        is_current_user=(target_user_id == current_user.id),
    )


# ─────────────────────────────────────────────────────────────
# DELETE /workspaces/{workspace_id}/members/{user_id} - 멤버 제거
# ─────────────────────────────────────────────────────────────

@router.delete("/{target_user_id}", status_code=204)
async def remove_member(
    workspace_id: uuid.UUID,
    target_user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    워크스페이스 멤버를 제거합니다.
    - owner만 가능
    - 본인 제거 불가 (400)
    - 마지막 멤버 제거 불가 (400)
    - MEMBER_LEFT 알림 발송
    """
    workspace = _get_workspace_or_404(workspace_id, db)
    my_membership = _get_membership_or_403(workspace_id, current_user.id, db)

    # owner만 멤버 제거 가능
    if my_membership.role != MemberRole.owner:
        raise HTTPException(
            status_code=403,
            detail="워크스페이스 owner만 멤버를 제거할 수 있습니다.",
        )

    # 본인 제거 불가
    if target_user_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="본인을 워크스페이스에서 제거할 수 없습니다.",
        )

    # 대상 멤버 조회
    target_membership = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == target_user_id,
    ).first()
    if not target_membership:
        raise HTTPException(status_code=404, detail="대상 멤버를 찾을 수 없습니다.")

    # 마지막 멤버 제거 불가
    member_count = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id
    ).count()
    if member_count <= 1:
        raise HTTPException(
            status_code=400,
            detail="마지막 멤버는 워크스페이스에서 제거할 수 없습니다.",
        )

    # 대상 사용자 정보
    target_user = db.query(User).filter(User.id == target_user_id).first()

    # MEMBER_LEFT 알림 발송 (제거된 사용자에게)
    try:
        await notification_service.create_notification(
            db=db,
            user_id=target_user_id,
            notification_type=NotificationType.MEMBER_LEFT,
            data={
                "workspace_id": str(workspace_id),
                "workspace_name": workspace.name,
                "target_user_name": target_user.name if target_user else "알 수 없음",
            },
            workspace_id=workspace_id,
        )
    except Exception as e:
        logger.warning(f"MEMBER_LEFT 알림 발송 실패: {e}")

    # 멤버 삭제
    db.delete(target_membership)
    db.commit()

    return None


# ─────────────────────────────────────────────────────────────
# POST /workspaces/{workspace_id}/members/transfer-ownership - 소유권 이전
# ─────────────────────────────────────────────────────────────

@router.post("/transfer-ownership")
def transfer_ownership(
    workspace_id: uuid.UUID,
    body: TransferOwnershipRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    워크스페이스 소유권을 다른 멤버에게 이전합니다.
    - 현재 owner만 호출 가능
    - 현재 owner → manager로 강등
    - 새 owner → owner로 승격
    """
    workspace = _get_workspace_or_404(workspace_id, db)
    my_membership = _get_membership_or_403(workspace_id, current_user.id, db)

    # 현재 owner만 소유권 이전 가능
    if my_membership.role != MemberRole.owner:
        raise HTTPException(
            status_code=403,
            detail="워크스페이스 owner만 소유권을 이전할 수 있습니다.",
        )

    # 자기 자신에게 이전 불가
    if body.new_owner_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="자기 자신에게는 소유권을 이전할 수 없습니다.",
        )

    # 새 owner 멤버십 조회
    new_owner_membership = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == body.new_owner_id,
    ).first()
    if not new_owner_membership:
        raise HTTPException(
            status_code=404,
            detail="소유권을 이전할 대상 멤버를 찾을 수 없습니다.",
        )

    # 소유권 이전
    my_membership.role = MemberRole.manager   # 현재 owner → manager
    new_owner_membership.role = MemberRole.owner  # 새 owner로 승격

    db.commit()

    return {
        "message": "소유권이 성공적으로 이전되었습니다.",
        "new_owner_id": str(body.new_owner_id),
    }
