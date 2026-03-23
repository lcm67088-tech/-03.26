"""
어드민 워크스페이스 관리 라우터 (Sprint 9)

엔드포인트 목록:
  GET    /admin/workspaces                      워크스페이스 목록 (필터·페이지네이션)
  GET    /admin/workspaces/{workspace_id}       워크스페이스 상세
  PATCH  /admin/workspaces/{workspace_id}/plan  플랜 강제 변경
  POST   /admin/workspaces/{workspace_id}/deactivate  소프트 삭제(비활성화)
  GET    /admin/workspaces/export/csv           CSV 내보내기

제약 사항:
  - 모든 엔드포인트에 require_admin 적용
  - 플랜 변경 시 BillingHistory 레코드 생성 (선택 가능)
  - 플랜 변경 시 NotificationService로 알림 발송
  - 비활성화 시 내부 멤버들에게 알림 발송
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
from app.core.dependencies import require_admin
from app.models.order import Order
from app.models.place import Place
from app.models.subscription import BillingHistory
from app.models.user import User
from app.models.workspace import MemberRole, Workspace, WorkspaceMember, WorkspacePlan
from app.schemas.admin_advanced import (
    AdminWorkspaceBillingItem,
    AdminWorkspaceDeactivate,
    AdminWorkspaceDetail,
    AdminWorkspaceListItem,
    AdminWorkspaceListResponse,
    AdminWorkspaceMemberSummary,
    AdminWorkspacePlanPatch,
    AdminWorkspacePlaceSummary,
)

router = APIRouter(prefix="/admin/workspaces", tags=["어드민-워크스페이스관리"])


# ============================================================
# Helper: 워크스페이스 목록 아이템 빌드
# ============================================================

def _build_workspace_list_item(ws: Workspace, db: Session) -> AdminWorkspaceListItem:
    """Workspace ORM → AdminWorkspaceListItem 변환"""
    owner = db.query(User).filter(User.id == ws.owner_id).first()
    owner_email = owner.email if owner else ""
    owner_name = owner.name if owner else ""

    member_count = db.query(func.count(WorkspaceMember.id)).filter(
        WorkspaceMember.workspace_id == ws.id
    ).scalar() or 0

    place_count = db.query(func.count(Place.id)).filter(
        Place.workspace_id == ws.id
    ).scalar() or 0

    order_count = db.query(func.count(Order.id)).filter(
        Order.workspace_id == ws.id
    ).scalar() or 0

    # 이번 달 청구 금액 (paid BillingHistory)
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    monthly_spend = db.query(func.coalesce(func.sum(BillingHistory.amount), 0)).filter(
        BillingHistory.workspace_id == ws.id,
        BillingHistory.status == "paid",
        BillingHistory.created_at >= month_start,
    ).scalar() or 0

    plan_val = ws.plan.value if hasattr(ws.plan, "value") else str(ws.plan)

    return AdminWorkspaceListItem(
        id=str(ws.id),
        name=ws.name,
        slug=str(ws.id)[:8],        # slug 컬럼 없으면 id prefix 사용
        plan=plan_val,
        is_active=ws.is_active,
        owner_id=str(ws.owner_id),
        owner_email=owner_email,
        owner_name=owner_name,
        member_count=member_count,
        place_count=place_count,
        order_count=order_count,
        monthly_spend=monthly_spend,
        created_at=ws.created_at,
        updated_at=ws.updated_at,
    )


# ============================================================
# GET /admin/workspaces — 워크스페이스 목록
# ============================================================

@router.get("", response_model=AdminWorkspaceListResponse, summary="워크스페이스 목록 조회")
async def list_workspaces(
    search: Optional[str] = Query(None, description="워크스페이스명/소유자 이메일 검색"),
    plan: Optional[str] = Query(None, description="플랜 필터 (free/starter/pro/enterprise)"),
    is_active: Optional[bool] = Query(None, description="활성화 여부 필터"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    sort: str = Query("created_at_desc", description="정렬 기준"),
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminWorkspaceListResponse:
    """워크스페이스 목록을 필터·페이지네이션으로 조회합니다."""
    query = db.query(Workspace)

    if search:
        pattern = f"%{search}%"
        owner_ids = db.query(User.id).filter(
            (User.email.ilike(pattern)) | (User.name.ilike(pattern))
        ).subquery()
        query = query.filter(
            (Workspace.name.ilike(pattern)) | (Workspace.owner_id.in_(owner_ids))
        )

    if plan:
        try:
            plan_enum = WorkspacePlan(plan)
            query = query.filter(Workspace.plan == plan_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"유효하지 않은 플랜: {plan}",
            )

    if is_active is not None:
        query = query.filter(Workspace.is_active == is_active)

    if sort == "created_at_asc":
        query = query.order_by(Workspace.created_at.asc())
    elif sort == "name_asc":
        query = query.order_by(Workspace.name.asc())
    else:
        query = query.order_by(Workspace.created_at.desc())

    total = query.count()
    workspaces = query.offset(skip).limit(limit).all()
    items = [_build_workspace_list_item(ws, db) for ws in workspaces]

    return AdminWorkspaceListResponse(total=total, items=items)


# ============================================================
# GET /admin/workspaces/export/csv — CSV 내보내기
# ============================================================

@router.get("/export/csv", summary="워크스페이스 CSV 내보내기")
async def export_workspaces_csv(
    search: Optional[str] = Query(None),
    plan: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """워크스페이스 전체 목록을 CSV로 내보냅니다."""
    query = db.query(Workspace)
    if search:
        pattern = f"%{search}%"
        owner_ids = db.query(User.id).filter(
            (User.email.ilike(pattern)) | (User.name.ilike(pattern))
        ).subquery()
        query = query.filter(
            (Workspace.name.ilike(pattern)) | (Workspace.owner_id.in_(owner_ids))
        )
    if plan:
        try:
            plan_enum = WorkspacePlan(plan)
            query = query.filter(Workspace.plan == plan_enum)
        except ValueError:
            pass
    if is_active is not None:
        query = query.filter(Workspace.is_active == is_active)

    query = query.order_by(Workspace.created_at.desc())
    workspaces = query.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "워크스페이스명", "플랜", "활성화",
        "소유자ID", "소유자이메일", "소유자이름",
        "멤버수", "플레이스수", "주문수", "이번달청구",
        "생성일시", "수정일시",
    ])
    for ws in workspaces:
        item = _build_workspace_list_item(ws, db)
        writer.writerow([
            item.id, item.name, item.plan,
            "Y" if item.is_active else "N",
            item.owner_id, item.owner_email, item.owner_name,
            item.member_count, item.place_count,
            item.order_count, item.monthly_spend,
            item.created_at.isoformat() if item.created_at else "",
            item.updated_at.isoformat() if item.updated_at else "",
        ])

    output.seek(0)
    today = datetime.utcnow().strftime("%Y%m%d")
    filename = f"export_workspaces_{today}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ============================================================
# GET /admin/workspaces/{workspace_id} — 워크스페이스 상세
# ============================================================

@router.get("/{workspace_id}", response_model=AdminWorkspaceDetail, summary="워크스페이스 상세 조회")
async def get_workspace(
    workspace_id: UUID,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminWorkspaceDetail:
    """워크스페이스 상세 정보 (멤버·플레이스·빌링 내역 포함)를 반환합니다."""
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다",
        )

    owner = db.query(User).filter(User.id == ws.owner_id).first()

    # 멤버 목록
    members_orm = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == ws.id
    ).all()
    members = []
    for m in members_orm:
        member_user = db.query(User).filter(User.id == m.user_id).first()
        members.append(AdminWorkspaceMemberSummary(
            id=str(m.id),
            user_id=str(m.user_id),
            user_email=member_user.email if member_user else "",
            user_name=member_user.name if member_user else "",
            role=m.role.value if hasattr(m.role, "value") else str(m.role),
            joined_at=m.created_at,
        ))

    # 플레이스 목록
    places_orm = db.query(Place).filter(
        Place.workspace_id == ws.id
    ).order_by(Place.created_at.desc()).all()

    places = []
    for pl in places_orm:
        from app.models.keyword import PlaceKeyword
        kw_count = db.query(func.count(PlaceKeyword.id)).filter(
            PlaceKeyword.place_id == pl.id
        ).scalar() or 0
        places.append(AdminWorkspacePlaceSummary(
            id=str(pl.id),
            name=pl.name,
            alias=pl.alias,
            naver_place_id=pl.naver_place_id or "",
            category=pl.category,
            is_active=pl.is_active if hasattr(pl, "is_active") else True,
            keyword_count=kw_count,
            created_at=pl.created_at,
        ))

    # 최근 빌링 내역 10개
    billing_orm = db.query(BillingHistory).filter(
        BillingHistory.workspace_id == ws.id
    ).order_by(BillingHistory.created_at.desc()).limit(10).all()

    recent_billing = []
    for b in billing_orm:
        recent_billing.append(AdminWorkspaceBillingItem(
            id=str(b.id),
            type=b.type.value if hasattr(b.type, "value") else str(b.type),
            plan=b.plan.value if hasattr(b.plan, "value") else str(b.plan),
            amount=b.amount,
            status=b.status.value if hasattr(b.status, "value") else str(b.status),
            description=b.description,
            created_at=b.created_at,
        ))

    # 집계
    order_count = db.query(func.count(Order.id)).filter(
        Order.workspace_id == ws.id
    ).scalar() or 0

    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    monthly_spend = db.query(func.coalesce(func.sum(BillingHistory.amount), 0)).filter(
        BillingHistory.workspace_id == ws.id,
        BillingHistory.status == "paid",
        BillingHistory.created_at >= month_start,
    ).scalar() or 0

    plan_val = ws.plan.value if hasattr(ws.plan, "value") else str(ws.plan)

    return AdminWorkspaceDetail(
        id=str(ws.id),
        name=ws.name,
        slug=str(ws.id)[:8],
        plan=plan_val,
        is_active=ws.is_active,
        owner_id=str(ws.owner_id),
        owner_email=owner.email if owner else "",
        owner_name=owner.name if owner else "",
        member_count=len(members),
        place_count=len(places),
        order_count=order_count,
        monthly_spend=monthly_spend,
        members=members,
        places=places,
        recent_billing=recent_billing,
        created_at=ws.created_at,
        updated_at=ws.updated_at,
    )


# ============================================================
# PATCH /admin/workspaces/{workspace_id}/plan — 플랜 강제 변경
# ============================================================

@router.patch(
    "/{workspace_id}/plan",
    summary="워크스페이스 플랜 강제 변경",
)
async def patch_workspace_plan(
    workspace_id: UUID,
    body: AdminWorkspacePlanPatch,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    워크스페이스 플랜을 강제 변경합니다.
    - BillingHistory 레코드 생성 (create_billing_record=True 시)
    - NotificationService 알림 발송
    """
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다",
        )

    try:
        new_plan = WorkspacePlan(body.plan)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"유효하지 않은 플랜: {body.plan}",
        )

    old_plan = ws.plan.value if hasattr(ws.plan, "value") else str(ws.plan)
    ws.plan = new_plan
    ws.updated_at = datetime.utcnow()

    # BillingHistory 레코드 생성 (선택)
    if body.create_billing_record:
        import uuid
        from app.models.subscription import BillingHistory as BH
        # plan 요금표 (심플)
        plan_price_map = {
            "free": 0,
            "starter": 49000,
            "pro": 149000,
            "enterprise": 499000,
        }
        amount = plan_price_map.get(body.plan, 0)
        billing = BH(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            subscription_id=None,
            type="upgrade" if amount > plan_price_map.get(old_plan, 0) else "downgrade",
            plan=new_plan,
            billing_cycle="monthly",
            amount=amount,
            status="paid",
            description=f"[어드민 강제변경] {old_plan} → {body.plan} / 사유: {body.reason}",
        )
        db.add(billing)

    db.commit()
    db.refresh(ws)

    # 알림 발송 (NotificationService 사용)
    try:
        from app.services.notification import NotificationService
        from app.models.notification import NotificationType
        ns = NotificationService(db)
        ns.create_notification(
            workspace_id=ws.id,
            type=NotificationType.PLAN_CHANGED,
            title="플랜이 변경되었습니다",
            message=f"워크스페이스 플랜이 {old_plan} → {body.plan}으로 변경되었습니다.",
            data={"old_plan": old_plan, "new_plan": body.plan, "reason": body.reason},
        )
    except Exception as e:
        print(f"[Notification] 플랜 변경 알림 발송 오류: {e}")

    return {
        "workspace_id": str(ws.id),
        "workspace_name": ws.name,
        "old_plan": old_plan,
        "new_plan": body.plan,
        "reason": body.reason,
        "billing_created": body.create_billing_record,
        "changed_by": str(current_admin.id),
        "message": f"플랜이 {old_plan} → {body.plan}으로 변경되었습니다",
    }


# ============================================================
# POST /admin/workspaces/{workspace_id}/deactivate — 소프트 삭제
# ============================================================

@router.post(
    "/{workspace_id}/deactivate",
    summary="워크스페이스 비활성화 (소프트 삭제)",
)
async def deactivate_workspace(
    workspace_id: UUID,
    body: AdminWorkspaceDeactivate,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    워크스페이스를 소프트 삭제합니다 (is_active=False).
    - 진행 중인 주문(in_progress) 이 있으면 400 오류
    - 워크스페이스 멤버들에게 비활성화 알림 발송
    """
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다",
        )

    if not ws.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 비활성화된 워크스페이스입니다",
        )

    # 진행 중인 주문 체크
    from app.models.order import OrderStatus
    active_orders = db.query(Order).filter(
        Order.workspace_id == ws.id,
        Order.status.in_([OrderStatus.IN_PROGRESS, OrderStatus.CONFIRMED]),
    ).count()
    if active_orders > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"진행 중인 주문({active_orders}건)이 있어 비활성화할 수 없습니다",
        )

    ws.is_active = False
    ws.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(ws)

    # 멤버들에게 알림 발송
    try:
        from app.services.notification import NotificationService
        from app.models.notification import NotificationType
        ns = NotificationService(db)
        ns.create_notification(
            workspace_id=ws.id,
            type=NotificationType.WORKSPACE_DEACTIVATED,
            title="워크스페이스가 비활성화되었습니다",
            message=f"워크스페이스 '{ws.name}'이 비활성화되었습니다. 사유: {body.reason}",
            data={"reason": body.reason, "deactivated_by": str(current_admin.id)},
        )
    except Exception as e:
        print(f"[Notification] 워크스페이스 비활성화 알림 발송 오류: {e}")

    return {
        "workspace_id": str(ws.id),
        "workspace_name": ws.name,
        "is_active": ws.is_active,
        "reason": body.reason,
        "message": f"워크스페이스 '{ws.name}'이 비활성화되었습니다",
    }
