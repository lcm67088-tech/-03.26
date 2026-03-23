"""
어드민 유저 관리 라우터 (Sprint 9)

엔드포인트 목록:
  GET    /admin/users               유저 목록 (필터·페이지네이션, require_admin)
  GET    /admin/users/{user_id}     유저 상세 (require_admin)
  PATCH  /admin/users/{user_id}/role    역할 변경 (require_superadmin)
  PATCH  /admin/users/{user_id}/status  활성/비활성 변경 (require_admin)
  POST   /admin/users/{user_id}/force-logout  강제 로그아웃 (require_admin)
  GET    /admin/users/export/csv    유저 목록 CSV 내보내기 (require_admin)

제약 사항:
  - 역할(role) 변경은 superadmin만 가능
  - 자기 자신의 역할·상태 변경 불가
  - 비활성 계정은 403 응답 (get_current_user에서 처리됨)
"""

import csv
import io
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin, require_superadmin
from app.core.redis import redis_client
from app.models.order import Order
from app.models.user import User, UserRole
from app.models.workspace import Workspace
from app.schemas.admin_advanced import (
    AdminUserDetail,
    AdminUserListItem,
    AdminUserListResponse,
    AdminUserOrderSummary,
    AdminUserRolePatch,
    AdminUserStatusPatch,
    AdminUserWorkspaceSummary,
)

router = APIRouter(prefix="/admin/users", tags=["어드민-유저관리"])


# ============================================================
# Helper: 유저 목록 아이템 빌드
# ============================================================

def _build_user_list_item(user: User, db: Session) -> AdminUserListItem:
    """User ORM 객체 → AdminUserListItem 변환"""
    workspace_count = db.query(func.count(Workspace.id)).filter(
        Workspace.owner_id == user.id
    ).scalar() or 0

    order_count = db.query(func.count(Order.id)).filter(
        Order.workspace_id.in_(
            db.query(Workspace.id).filter(Workspace.owner_id == user.id)
        )
    ).scalar() or 0

    return AdminUserListItem(
        id=str(user.id),
        email=user.email,
        name=user.name,
        phone=user.phone,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
        is_active=user.is_active,
        email_verified=user.email_verified,
        workspace_count=workspace_count,
        order_count=order_count,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


# ============================================================
# GET /admin/users — 유저 목록
# ============================================================

@router.get("", response_model=AdminUserListResponse, summary="유저 목록 조회")
async def list_users(
    # 검색·필터
    search: Optional[str] = Query(None, description="이메일/이름 검색"),
    role: Optional[str] = Query(None, description="역할 필터 (user/admin/superadmin)"),
    is_active: Optional[bool] = Query(None, description="활성화 여부 필터"),
    # 페이지네이션
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    # 정렬
    sort: str = Query("created_at_desc", description="정렬 기준 (created_at_desc/created_at_asc/name_asc)"),
    # 의존성
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminUserListResponse:
    """
    유저 목록을 페이지네이션·필터·검색으로 조회합니다.
    """
    query = db.query(User)

    # 검색 (이메일 OR 이름)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            (User.email.ilike(pattern)) | (User.name.ilike(pattern))
        )

    # 역할 필터
    if role:
        try:
            role_enum = UserRole(role)
            query = query.filter(User.role == role_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"유효하지 않은 역할: {role}",
            )

    # 활성화 여부 필터
    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    # 정렬
    if sort == "created_at_asc":
        query = query.order_by(User.created_at.asc())
    elif sort == "name_asc":
        query = query.order_by(User.name.asc())
    else:
        query = query.order_by(User.created_at.desc())

    total = query.count()
    users = query.offset(skip).limit(limit).all()

    items = [_build_user_list_item(u, db) for u in users]

    return AdminUserListResponse(total=total, items=items)


# ============================================================
# GET /admin/users/export/csv — CSV 내보내기
# ============================================================

@router.get("/export/csv", summary="유저 목록 CSV 내보내기")
async def export_users_csv(
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """유저 전체 목록을 CSV로 내보냅니다."""
    query = db.query(User)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            (User.email.ilike(pattern)) | (User.name.ilike(pattern))
        )
    if role:
        try:
            role_enum = UserRole(role)
            query = query.filter(User.role == role_enum)
        except ValueError:
            pass
    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    query = query.order_by(User.created_at.desc())
    users = query.all()

    # CSV 스트림 생성
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "이메일", "이름", "전화번호", "역할",
        "활성화", "이메일인증", "가입일시", "수정일시",
    ])
    for u in users:
        role_val = u.role.value if hasattr(u.role, "value") else str(u.role)
        writer.writerow([
            str(u.id),
            u.email,
            u.name,
            u.phone or "",
            role_val,
            "Y" if u.is_active else "N",
            "Y" if u.email_verified else "N",
            u.created_at.isoformat() if u.created_at else "",
            u.updated_at.isoformat() if u.updated_at else "",
        ])

    output.seek(0)
    today = datetime.utcnow().strftime("%Y%m%d")
    filename = f"export_users_{today}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ============================================================
# GET /admin/users/{user_id} — 유저 상세
# ============================================================

@router.get("/{user_id}", response_model=AdminUserDetail, summary="유저 상세 조회")
async def get_user(
    user_id: UUID,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminUserDetail:
    """
    특정 유저의 상세 정보를 반환합니다.
    소유 워크스페이스 및 최근 주문 10개 포함.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="유저를 찾을 수 없습니다",
        )

    # 소유 워크스페이스 목록
    workspaces_orm = db.query(Workspace).filter(
        Workspace.owner_id == user.id
    ).order_by(Workspace.created_at.desc()).all()

    workspaces = []
    for ws in workspaces_orm:
        from app.models.workspace import WorkspaceMember
        from app.models.place import Place
        member_count = db.query(func.count(WorkspaceMember.id)).filter(
            WorkspaceMember.workspace_id == ws.id
        ).scalar() or 0
        place_count = db.query(func.count(Place.id)).filter(
            Place.workspace_id == ws.id
        ).scalar() or 0
        workspaces.append(AdminUserWorkspaceSummary(
            id=str(ws.id),
            name=ws.name,
            plan=ws.plan.value if hasattr(ws.plan, "value") else str(ws.plan),
            is_active=ws.is_active,
            member_count=member_count,
            place_count=place_count,
            created_at=ws.created_at,
        ))

    # 최근 주문 10개
    ws_ids = [ws.id for ws in workspaces_orm]
    recent_orders = []
    if ws_ids:
        orders_orm = db.query(Order).filter(
            Order.workspace_id.in_(ws_ids)
        ).order_by(Order.created_at.desc()).limit(10).all()

        for o in orders_orm:
            ws_name = next((ws.name for ws in workspaces_orm if ws.id == o.workspace_id), "")
            recent_orders.append(AdminUserOrderSummary(
                id=str(o.id),
                product_name=o.product_name or "",
                status=o.status.value if hasattr(o.status, "value") else str(o.status),
                total_amount=o.total_amount or 0,
                workspace_name=ws_name,
                ordered_at=o.ordered_at,
                created_at=o.created_at,
            ))

    total_order_count = db.query(func.count(Order.id)).filter(
        Order.workspace_id.in_([ws.id for ws in workspaces_orm])
    ).scalar() or 0 if workspaces_orm else 0

    role_val = user.role.value if hasattr(user.role, "value") else str(user.role)

    return AdminUserDetail(
        id=str(user.id),
        email=user.email,
        name=user.name,
        phone=user.phone,
        role=role_val,
        is_active=user.is_active,
        email_verified=user.email_verified,
        workspaces=workspaces,
        recent_orders=recent_orders,
        workspace_count=len(workspaces),
        order_count=total_order_count,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


# ============================================================
# PATCH /admin/users/{user_id}/role — 역할 변경 (superadmin 전용)
# ============================================================

@router.patch(
    "/{user_id}/role",
    summary="유저 역할 변경 (슈퍼어드민 전용)",
)
async def patch_user_role(
    user_id: UUID,
    body: AdminUserRolePatch,
    current_admin: User = Depends(require_superadmin),  # superadmin 전용
    db: Session = Depends(get_db),
):
    """
    유저의 역할을 변경합니다.
    - superadmin 권한 필요
    - 자기 자신 변경 불가
    """
    if str(user_id) == str(current_admin.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="자기 자신의 역할을 변경할 수 없습니다",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="유저를 찾을 수 없습니다",
        )

    try:
        new_role = UserRole(body.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"유효하지 않은 역할: {body.role}",
        )

    old_role = user.role.value if hasattr(user.role, "value") else str(user.role)
    user.role = new_role
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    return {
        "user_id": str(user.id),
        "email": user.email,
        "old_role": old_role,
        "new_role": body.role,
        "reason": body.reason,
        "changed_by": str(current_admin.id),
        "message": f"역할이 {old_role} → {body.role}로 변경되었습니다",
    }


# ============================================================
# PATCH /admin/users/{user_id}/status — 활성/비활성 변경
# ============================================================

@router.patch(
    "/{user_id}/status",
    summary="유저 활성/비활성 변경",
)
async def patch_user_status(
    user_id: UUID,
    body: AdminUserStatusPatch,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    유저의 활성화 상태를 변경합니다.
    - 자기 자신 변경 불가
    - 비활성화 시 해당 유저 토큰 강제 만료 처리
    """
    if str(user_id) == str(current_admin.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="자기 자신의 상태를 변경할 수 없습니다",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="유저를 찾을 수 없습니다",
        )

    old_status = user.is_active
    user.is_active = body.is_active
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    # 비활성화 시 Redis에서 해당 유저 토큰 블랙리스트 처리
    if not body.is_active and redis_client:
        try:
            # user_id 기반 토큰 무효화 키 설정
            blacklist_key = f"user_blacklist:{user.id}"
            redis_client.set(blacklist_key, "1", ex=86400 * 30)  # 30일
        except Exception as e:
            print(f"[Redis] 토큰 무효화 오류: {e}")

    status_text = "활성화" if body.is_active else "비활성화"
    return {
        "user_id": str(user.id),
        "email": user.email,
        "is_active": user.is_active,
        "reason": body.reason,
        "message": f"계정이 {status_text}되었습니다",
    }


# ============================================================
# POST /admin/users/{user_id}/force-logout — 강제 로그아웃
# ============================================================

@router.post(
    "/{user_id}/force-logout",
    summary="유저 강제 로그아웃",
)
async def force_logout_user(
    user_id: UUID,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    특정 유저를 강제 로그아웃시킵니다.
    Redis에 해당 user_id 블랙리스트 키를 설정하여
    이후 모든 토큰 요청이 거부되도록 합니다.
    """
    if str(user_id) == str(current_admin.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="자기 자신을 강제 로그아웃할 수 없습니다",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="유저를 찾을 수 없습니다",
        )

    # Redis 블랙리스트 설정 (access token 만료 시간 기준 24시간)
    if redis_client:
        try:
            blacklist_key = f"user_blacklist:{user.id}"
            redis_client.set(blacklist_key, "force_logout", ex=86400)
        except Exception as e:
            print(f"[Redis] 강제 로그아웃 오류: {e}")

    return {
        "user_id": str(user.id),
        "email": user.email,
        "message": "강제 로그아웃 처리되었습니다. 다음 API 요청부터 거부됩니다.",
        "applied_by": str(current_admin.id),
    }
