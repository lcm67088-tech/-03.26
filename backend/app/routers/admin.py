"""
어드민 라우터 (Sprint 6 완성)

기존 GET /dashboard 유지 + 아래 엔드포인트 추가:

[주문 관리]
GET  /api/v1/admin/orders                       전체 주문 목록 (필터·페이지네이션)
GET  /api/v1/admin/orders/{order_id}            주문 상세 (어드민용)
PATCH /api/v1/admin/orders/{order_id}/status    주문 상태 변경 (상태 전이 검증)
POST /api/v1/admin/orders/{order_id}/assign     미디어사 배정
POST /api/v1/admin/orders/{order_id}/complete   주문 완료 처리 (증빙 URL)
POST /api/v1/admin/orders/{order_id}/refund     환불 결정 (승인/거부)

[미디어사 관리]
GET    /api/v1/admin/media-companies            목록 (통계 포함)
POST   /api/v1/admin/media-companies            등록
GET    /api/v1/admin/media-companies/{id}       상세 + 최근 주문 10개
PUT    /api/v1/admin/media-companies/{id}       수정
DELETE /api/v1/admin/media-companies/{id}       소프트 삭제

[기존 유지]
GET /api/v1/admin/dashboard
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.keyword import PlaceKeyword
from app.services.notification_service import notification_service  # Sprint 7
from app.models.media_company import MediaCompany
from app.models.order import Order, OrderStatus, Payment, PaymentStatus
from app.models.place import Place
from app.models.product import Product
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.admin import (
    AdminOrderDetail,
    AdminOrderListItem,
    AdminOrderListResponse,
    AdminPaymentInfo,
    AssignMediaCompany,
    CompleteOrder,
    MediaCompanyCreate,
    MediaCompanyDetail,
    MediaCompanyResponse,
    MediaCompanyUpdate,
    OrderStatusUpdate,
    RecentOrderForMedia,
    RefundDecision,
)

router = APIRouter()


# ============================
# 대시보드 응답 스키마 (기존 유지)
# ============================

class PlanDistribution(BaseModel):
    """플랜별 워크스페이스 수"""
    free: int
    starter: int
    pro: int
    enterprise: int


class AdminDashboardResponse(BaseModel):
    """어드민 대시보드 응답"""
    today_orders: int
    today_revenue: int
    pending_orders: int
    this_month_revenue: int
    total_workspaces: int
    active_workspaces: int
    plan_distribution: PlanDistribution
    recent_orders: list[dict[str, Any]]


# ============================
# 허용 상태 전이 테이블
# ============================

# 키: 현재 상태, 값: 전환 가능한 상태 집합
ALLOWED_TRANSITIONS: Dict[OrderStatus, set] = {
    OrderStatus.CONFIRMED:   {OrderStatus.IN_PROGRESS, OrderStatus.CANCELLED, OrderStatus.DISPUTED},
    OrderStatus.IN_PROGRESS: {OrderStatus.COMPLETED,   OrderStatus.CANCELLED, OrderStatus.DISPUTED},
    OrderStatus.COMPLETED:   {OrderStatus.DISPUTED},
    # pending → confirmed 는 결제 완료 엔드포인트에서만 처리
}


# ============================
# 내부 헬퍼 — admin_notes append
# ============================

def _append_admin_note(order: Order, note: str, admin_id: str) -> None:
    """
    order.extra_data['admin_notes'] 배열에 노트 추가.
    extra_data가 None이면 초기화.
    """
    if not order.extra_data:
        order.extra_data = {}
    notes: list = order.extra_data.get("admin_notes", [])
    notes.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "note": note,
        "admin_id": admin_id,
    })
    # SQLAlchemy JSONB 변경 감지를 위한 새 dict 할당
    order.extra_data = {**order.extra_data, "admin_notes": notes}


# ============================
# 내부 헬퍼 — Order → AdminOrderDetail 변환
# ============================

def _order_to_admin_detail(order: Order, db: Session) -> AdminOrderDetail:
    """Order 모델을 AdminOrderDetail 스키마로 변환"""
    # 워크스페이스 정보
    ws = db.query(Workspace).filter(Workspace.id == order.workspace_id).first()
    workspace_info = None
    if ws:
        workspace_info = {
            "id": str(ws.id),
            "name": ws.name,
            "plan": ws.plan.value if hasattr(ws.plan, "value") else str(ws.plan),
        }

    # 장소 정보
    place_info = None
    if order.place_id:
        place = db.query(Place).filter(Place.id == order.place_id).first()
        if place:
            place_info = {
                "id": str(place.id),
                "name": place.name,
                "alias": place.alias,
                "naver_place_id": place.naver_place_id,
            }

    # 키워드 정보
    keyword_infos: list = []
    if order.keyword_ids:
        for kw_id in order.keyword_ids:
            try:
                kw = db.query(PlaceKeyword).filter(
                    PlaceKeyword.id == kw_id
                ).first()
                if kw:
                    keyword_infos.append({"id": str(kw.id), "keyword": kw.keyword})
            except Exception:
                pass

    # 결제 정보
    payment_info = None
    if order.payment:
        p = order.payment
        payment_info = AdminPaymentInfo(
            id=str(p.id),
            amount=p.amount,
            method=p.method.value if p.method else None,
            status=p.status.value,
            pg_transaction_id=p.pg_transaction_id,
            paid_at=p.paid_at,
            created_at=p.created_at,
        )

    # 미디어사 정보
    media_info = None
    if order.media_company_id:
        mc = db.query(MediaCompany).filter(
            MediaCompany.id == order.media_company_id
        ).first()
        if mc:
            media_info = {"id": str(mc.id), "name": mc.name}

    # 어드민 노트
    admin_notes: list = []
    if order.extra_data and isinstance(order.extra_data.get("admin_notes"), list):
        admin_notes = order.extra_data["admin_notes"]

    return AdminOrderDetail(
        id=str(order.id),
        product_id=str(order.product_id) if order.product_id else None,
        product_name=order.product_name,
        description=order.description,
        status=order.status.value,
        quantity=order.quantity,
        unit_price=order.unit_price,
        total_amount=order.total_amount,
        special_requests=order.special_requests,
        proof_url=order.proof_url,
        workspace=workspace_info,
        place=place_info,
        keywords=keyword_infos,
        payment=payment_info,
        media_company=media_info,
        admin_notes=admin_notes,
        ordered_at=order.ordered_at,
        completed_at=order.completed_at,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


# ============================
# 내부 헬퍼 — MediaCompany 통계 계산
# ============================

def _calc_media_stats(mc: MediaCompany, db: Session) -> Dict[str, Any]:
    """
    매체사의 주문 통계 계산:
    - order_count: 배정된 총 주문 수
    - completed_count: 완료된 주문 수
    - avg_completion_days: 평균 처리 기간 (일)
    """
    orders = db.query(Order).filter(
        Order.media_company_id == mc.id
    ).all()

    order_count = len(orders)
    completed = [o for o in orders if o.status == OrderStatus.COMPLETED]
    completed_count = len(completed)

    # 평균 처리 기간 계산 (ordered_at → completed_at)
    days_list = []
    for o in completed:
        if o.ordered_at and o.completed_at:
            delta = (o.completed_at - o.ordered_at).total_seconds() / 86400
            if delta >= 0:
                days_list.append(delta)

    avg_days: Optional[float] = None
    if days_list:
        avg_days = round(sum(days_list) / len(days_list), 1)

    return {
        "order_count": order_count,
        "completed_count": completed_count,
        "avg_completion_days": avg_days,
    }


# ============================
# 어드민 대시보드 (기존 유지)
# ============================

@router.get("/dashboard", response_model=AdminDashboardResponse)
async def get_admin_dashboard(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    어드민 대시보드 데이터.

    - 오늘 주문 수 / 매출
    - 처리 대기 주문 수 (confirmed 상태)
    - 이번달 매출
    - 전체 / 활성 워크스페이스 수
    - 플랜별 분포
    - 최근 주문 5개
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    thirty_days_ago = now - timedelta(days=30)

    # 오늘 신규 주문 수
    today_orders = db.query(func.count(Order.id)).filter(
        Order.created_at >= today_start,
        Order.status.notin_([OrderStatus.CANCELLED, OrderStatus.REFUNDED]),
    ).scalar() or 0

    # 오늘 매출 (완료된 주문)
    today_revenue = (
        db.query(func.coalesce(func.sum(Order.total_amount), 0))
        .filter(
            Order.ordered_at >= today_start,
            Order.status == OrderStatus.COMPLETED,
        )
        .scalar() or 0
    )

    # 처리 대기 주문 수 (confirmed 상태)
    pending_orders = db.query(func.count(Order.id)).filter(
        Order.status == OrderStatus.CONFIRMED,
    ).scalar() or 0

    # 이번달 매출
    this_month_revenue = (
        db.query(func.coalesce(func.sum(Order.total_amount), 0))
        .filter(
            Order.ordered_at >= month_start,
            Order.status == OrderStatus.COMPLETED,
        )
        .scalar() or 0
    )

    # 전체 워크스페이스 수
    total_workspaces = db.query(func.count(Workspace.id)).filter(
        Workspace.is_active == True,
    ).scalar() or 0

    # 활성 워크스페이스 수 (최근 30일 내 주문 있는)
    active_ws_ids = (
        db.query(Order.workspace_id)
        .filter(Order.created_at >= thirty_days_ago)
        .distinct()
        .subquery()
    )
    active_workspaces = db.query(func.count()).select_from(active_ws_ids).scalar() or 0

    # 플랜별 분포
    plan_counts: dict[str, int] = {}
    for plan_name in ("free", "starter", "pro", "enterprise"):
        cnt = db.query(func.count(Workspace.id)).filter(
            Workspace.plan == plan_name,
            Workspace.is_active == True,
        ).scalar() or 0
        plan_counts[plan_name] = cnt

    # 최근 주문 5개 (워크스페이스명 포함)
    recent_orders_db = (
        db.query(Order)
        .order_by(Order.created_at.desc())
        .limit(5)
        .all()
    )
    recent_orders = []
    for o in recent_orders_db:
        ws = db.query(Workspace).filter(Workspace.id == o.workspace_id).first()
        recent_orders.append({
            "id": str(o.id),
            "product_name": o.product_name,
            "status": o.status.value,
            "total_amount": o.total_amount,
            "ordered_at": o.ordered_at.isoformat() if o.ordered_at else None,
            "workspace_id": str(o.workspace_id),
            "workspace_name": ws.name if ws else "-",
        })

    return AdminDashboardResponse(
        today_orders=today_orders,
        today_revenue=today_revenue,
        pending_orders=pending_orders,
        this_month_revenue=this_month_revenue,
        total_workspaces=total_workspaces,
        active_workspaces=active_workspaces,
        plan_distribution=PlanDistribution(**plan_counts),
        recent_orders=recent_orders,
    )


# ============================
# 주문 목록 (어드민)
# ============================

@router.get(
    "/orders",
    response_model=AdminOrderListResponse,
    summary="전체 주문 목록 (어드민)",
)
async def list_all_orders(
    status_filter: Optional[str] = Query(
        None, alias="status", description="상태 필터"
    ),
    workspace_id: Optional[str] = Query(None, description="워크스페이스 ID 필터"),
    media_company_id: Optional[str] = Query(None, description="미디어사 ID 필터"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    모든 워크스페이스의 주문 목록 조회.

    - status, workspace_id, media_company_id 필터 지원
    - skip/limit 페이지네이션
    - 응답에 workspace_name, media_company_name 포함
    """
    query = db.query(Order)

    # 상태 필터
    if status_filter:
        try:
            status_enum = OrderStatus(status_filter)
            query = query.filter(Order.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"유효하지 않은 상태 값: {status_filter}",
            )

    # 워크스페이스 필터
    if workspace_id:
        try:
            ws_uuid = uuid.UUID(workspace_id)
            query = query.filter(Order.workspace_id == ws_uuid)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="유효하지 않은 워크스페이스 ID 형식",
            )

    # 미디어사 필터
    if media_company_id:
        try:
            mc_uuid = uuid.UUID(media_company_id)
            query = query.filter(Order.media_company_id == mc_uuid)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="유효하지 않은 미디어사 ID 형식",
            )

    total = query.count()
    orders = (
        query.order_by(Order.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    items = []
    for order in orders:
        # 워크스페이스 정보
        ws = db.query(Workspace).filter(Workspace.id == order.workspace_id).first()
        ws_name = ws.name if ws else "-"
        ws_plan = (ws.plan.value if hasattr(ws.plan, "value") else str(ws.plan)) if ws else "free"

        # 장소 이름
        place_name = None
        if order.place_id:
            place = db.query(Place).filter(Place.id == order.place_id).first()
            if place:
                place_name = place.alias or place.name

        # 미디어사 이름
        mc_name = None
        if order.media_company_id:
            mc = db.query(MediaCompany).filter(
                MediaCompany.id == order.media_company_id
            ).first()
            if mc:
                mc_name = mc.name

        items.append(
            AdminOrderListItem(
                id=str(order.id),
                product_name=order.product_name,
                status=order.status.value,
                total_amount=order.total_amount,
                quantity=order.quantity,
                workspace_id=str(order.workspace_id),
                workspace_name=ws_name,
                workspace_plan=ws_plan,
                place_name=place_name,
                media_company_id=str(order.media_company_id) if order.media_company_id else None,
                media_company_name=mc_name,
                ordered_at=order.ordered_at,
                updated_at=order.updated_at,
                created_at=order.created_at,
            )
        )

    return AdminOrderListResponse(total=total, items=items)


# ============================
# 주문 상세 (어드민)
# ============================

@router.get(
    "/orders/{order_id}",
    response_model=AdminOrderDetail,
    summary="주문 상세 (어드민)",
)
async def get_order_admin(
    order_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """주문 상세 조회 (어드민 전용, 모든 정보 포함)"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="주문을 찾을 수 없습니다",
        )
    return _order_to_admin_detail(order, db)


# ============================
# 주문 상태 변경
# ============================

@router.patch(
    "/orders/{order_id}/status",
    summary="주문 상태 변경 (어드민)",
)
async def update_order_status(
    order_id: str,
    body: OrderStatusUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    주문 상태 변경.

    허용 전이:
        confirmed   → in_progress, cancelled, disputed
        in_progress → completed, cancelled, disputed
        completed   → disputed

    그 외 전이는 400 에러.
    note는 extra_data.admin_notes에 타임스탬프·관리자 ID와 함께 저장.
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="주문을 찾을 수 없습니다",
        )

    # 새 상태 파싱
    try:
        new_status = OrderStatus(body.status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"유효하지 않은 상태 값: {body.status}",
        )

    # 전이 유효성 검사
    allowed = ALLOWED_TRANSITIONS.get(order.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="허용되지 않는 상태 전환입니다.",
        )

    old_status = order.status.value
    order.status = new_status

    # in_progress → completed 시 completed_at 기록
    if new_status == OrderStatus.COMPLETED and not order.completed_at:
        order.completed_at = datetime.now(timezone.utc)

    # 노트 저장
    note_text = body.note or f"상태 변경: {old_status} → {new_status.value}"
    _append_admin_note(order, note_text, str(admin.id))

    db.commit()

    return {
        "order_id": str(order.id),
        "status": order.status.value,
        "message": f"주문 상태가 {new_status.value}(으)로 변경되었습니다",
    }


# ============================
# 미디어사 배정
# ============================

@router.post(
    "/orders/{order_id}/assign",
    summary="미디어사 배정 (어드민)",
)
async def assign_media_company(
    order_id: str,
    body: AssignMediaCompany,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    주문에 미디어사 배정.

    - 미디어사 존재 여부 확인
    - order.media_company_id 업데이트
    - order.status가 confirmed이면 → in_progress로 자동 전환
    - Mock 알림 출력
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="주문을 찾을 수 없습니다",
        )

    # 미디어사 확인
    try:
        mc_uuid = uuid.UUID(body.media_company_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="유효하지 않은 미디어사 ID 형식",
        )

    mc = db.query(MediaCompany).filter(
        MediaCompany.id == mc_uuid,
        MediaCompany.is_active == True,
    ).first()
    if not mc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="미디어사를 찾을 수 없습니다",
        )

    order.media_company_id = mc_uuid

    # confirmed → in_progress 자동 전환
    if order.status == OrderStatus.CONFIRMED:
        order.status = OrderStatus.IN_PROGRESS
        _append_admin_note(
            order,
            f"미디어사 배정: {mc.name} → 진행중으로 자동 전환",
            str(admin.id),
        )
    else:
        _append_admin_note(
            order,
            f"미디어사 배정 변경: {mc.name}",
            str(admin.id),
        )

    db.commit()

    # ── Sprint 7: 매체사 배정 알림 발송 ──────────────────────
    try:
        # 워크스페이스 오너에게 알림 발송
        from app.models.workspace import WorkspaceMember, MemberRole
        owner_membership = (
            db.query(WorkspaceMember)
            .filter(
                WorkspaceMember.workspace_id == order.workspace_id,
                WorkspaceMember.role == MemberRole.owner,
            )
            .first()
        )
        if owner_membership:
            order_user = db.query(User).filter(User.id == owner_membership.user_id).first()
            if order_user:
                await notification_service.notify_order_status_changed(
                    db, order, order_user, "assigned"
                )
                db.commit()
    except Exception as _e:
        import logging
        logging.getLogger(__name__).warning(f"매체사 배정 알림 발송 실패: {_e}")

    return {
        "order_id": str(order.id),
        "media_company_id": str(mc.id),
        "media_company_name": mc.name,
        "status": order.status.value,
    }


# ============================
# 주문 완료 처리
# ============================

@router.post(
    "/orders/{order_id}/complete",
    summary="주문 완료 처리 (어드민)",
)
async def complete_order_admin(
    order_id: str,
    body: CompleteOrder,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    주문 완료 처리.

    - order.status → completed
    - order.proof_url 저장
    - order.completed_at = now()
    - extra_data.completed = true (환불 방지 플래그)
    - Mock 알림 출력
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="주문을 찾을 수 없습니다",
        )

    # in_progress 또는 confirmed 상태에서만 완료 처리 가능
    if order.status not in (OrderStatus.IN_PROGRESS, OrderStatus.CONFIRMED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"현재 상태({order.status.value})에서는 완료 처리할 수 없습니다",
        )

    now = datetime.now(timezone.utc)
    order.status = OrderStatus.COMPLETED
    order.proof_url = body.proof_url
    order.completed_at = now

    # 완료 플래그 + 노트 저장
    _append_admin_note(order, f"작업 완료 처리 | 증빙: {body.proof_url}", str(admin.id))
    if not order.extra_data:
        order.extra_data = {}
    order.extra_data = {**order.extra_data, "completed": True}

    db.commit()

    # ── Sprint 7: 주문 완료 알림 발송 ────────────────────────
    try:
        from app.models.workspace import WorkspaceMember, MemberRole
        owner_membership = (
            db.query(WorkspaceMember)
            .filter(
                WorkspaceMember.workspace_id == order.workspace_id,
                WorkspaceMember.role == MemberRole.owner,
            )
            .first()
        )
        if owner_membership:
            order_user = db.query(User).filter(User.id == owner_membership.user_id).first()
            if order_user:
                await notification_service.notify_order_status_changed(
                    db, order, order_user, "completed"
                )
                db.commit()
    except Exception as _e:
        import logging
        logging.getLogger(__name__).warning(f"주문 완료 알림 발송 실패: {_e}")

    return {
        "order_id": str(order.id),
        "status": order.status.value,
        "proof_url": order.proof_url,
        "completed_at": order.completed_at.isoformat(),
    }


# ============================
# 환불 결정
# ============================

@router.post(
    "/orders/{order_id}/refund",
    summary="환불 결정 (어드민)",
)
async def decide_refund(
    order_id: str,
    body: RefundDecision,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    환불 결정 처리.

    approve=True:
        - order.status → refunded
        - payment.status → refunded

    approve=False:
        - order.status → confirmed (원상복구)
        - 환불 거부 사유 저장

    note를 admin_notes에 기록.
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="주문을 찾을 수 없습니다",
        )

    # disputed 상태에서만 환불 결정 가능
    if order.status != OrderStatus.DISPUTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"환불 요청(disputed) 상태에서만 처리 가능합니다. 현재: {order.status.value}",
        )

    if body.approve:
        # 환불 승인
        order.status = OrderStatus.REFUNDED
        if order.payment:
            order.payment.status = PaymentStatus.REFUNDED

        _append_admin_note(
            order,
            f"환불 승인 | 사유: {body.note}",
            str(admin.id),
        )
        result_msg = "환불이 승인되었습니다"
        new_status = "refunded"

    else:
        # 환불 거부 → confirmed 상태로 복구
        order.status = OrderStatus.CONFIRMED

        _append_admin_note(
            order,
            f"환불 거부 | 사유: {body.note}",
            str(admin.id),
        )
        result_msg = "환불 요청이 거부되었습니다. 주문이 확정 상태로 복구되었습니다"
        new_status = "confirmed"

    db.commit()

    # ── Sprint 7: 환불 결정 알림 발송 (승인 시에만) ─────────────────────────
    if body.approve:
        try:
            from app.models.workspace import WorkspaceMember, MemberRole
            owner_membership = (
                db.query(WorkspaceMember)
                .filter(
                    WorkspaceMember.workspace_id == order.workspace_id,
                    WorkspaceMember.role == MemberRole.owner,
                )
                .first()
            )
            if owner_membership:
                order_user = db.query(User).filter(User.id == owner_membership.user_id).first()
                if order_user:
                    await notification_service.notify_order_status_changed(
                        db, order, order_user, "refund_decided"
                    )
                    db.commit()
        except Exception as _e:
            import logging
            logging.getLogger(__name__).warning(f"환불 결정 알림 발송 실패: {_e}")

    return {
        "order_id": str(order.id),
        "status": new_status,
        "approved": body.approve,
        "message": result_msg,
    }


# ============================
# 미디어사 목록
# ============================

@router.get(
    "/media-companies",
    response_model=List[MediaCompanyResponse],
    summary="미디어사 목록 (어드민)",
)
async def list_media_companies(
    include_inactive: bool = Query(False, description="비활성 매체사 포함 여부"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    전체 미디어사 목록.
    각 미디어사의 주문 통계(order_count, completed_count, avg_completion_days) 포함.
    """
    query = db.query(MediaCompany)
    if not include_inactive:
        query = query.filter(MediaCompany.is_active == True)

    companies = query.order_by(MediaCompany.name).all()

    result = []
    for mc in companies:
        stats = _calc_media_stats(mc, db)
        result.append(
            MediaCompanyResponse(
                id=str(mc.id),
                name=mc.name,
                contact_email=mc.contact_email,
                contact_phone=mc.contact_phone,
                bank_account=mc.bank_account,
                is_active=mc.is_active,
                **stats,
            )
        )
    return result


# ============================
# 미디어사 등록
# ============================

@router.post(
    "/media-companies",
    response_model=MediaCompanyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="미디어사 등록 (어드민)",
)
async def create_media_company(
    body: MediaCompanyCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    미디어사 등록.
    이름 중복 체크 후 생성.
    """
    # 이름 중복 체크 (is_active 불문)
    existing = db.query(MediaCompany).filter(
        MediaCompany.name == body.name,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"이미 등록된 미디어사명입니다: {body.name}",
        )

    mc = MediaCompany(
        id=uuid.uuid4(),
        name=body.name,
        contact_email=body.contact_email,
        contact_phone=body.contact_phone,
        bank_account=body.bank_account,
        is_active=True,
    )
    db.add(mc)
    db.commit()
    db.refresh(mc)

    return MediaCompanyResponse(
        id=str(mc.id),
        name=mc.name,
        contact_email=mc.contact_email,
        contact_phone=mc.contact_phone,
        bank_account=mc.bank_account,
        is_active=mc.is_active,
        order_count=0,
        completed_count=0,
        avg_completion_days=None,
    )


# ============================
# 미디어사 상세
# ============================

@router.get(
    "/media-companies/{media_company_id}",
    response_model=MediaCompanyDetail,
    summary="미디어사 상세 (어드민)",
)
async def get_media_company(
    media_company_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    미디어사 상세 조회.
    통계 + 최근 주문 10개 포함.
    """
    mc = db.query(MediaCompany).filter(
        MediaCompany.id == media_company_id
    ).first()
    if not mc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="미디어사를 찾을 수 없습니다",
        )

    stats = _calc_media_stats(mc, db)

    # 최근 주문 10개
    recent_orders_db = (
        db.query(Order)
        .filter(Order.media_company_id == mc.id)
        .order_by(Order.created_at.desc())
        .limit(10)
        .all()
    )
    recent_orders = []
    for o in recent_orders_db:
        ws = db.query(Workspace).filter(Workspace.id == o.workspace_id).first()
        recent_orders.append(
            RecentOrderForMedia(
                id=str(o.id),
                product_name=o.product_name,
                status=o.status.value,
                total_amount=o.total_amount,
                workspace_name=ws.name if ws else "-",
                ordered_at=o.ordered_at,
                completed_at=o.completed_at,
            )
        )

    return MediaCompanyDetail(
        id=str(mc.id),
        name=mc.name,
        contact_email=mc.contact_email,
        contact_phone=mc.contact_phone,
        bank_account=mc.bank_account,
        is_active=mc.is_active,
        recent_orders=recent_orders,
        **stats,
    )


# ============================
# 미디어사 수정
# ============================

@router.put(
    "/media-companies/{media_company_id}",
    response_model=MediaCompanyResponse,
    summary="미디어사 수정 (어드민)",
)
async def update_media_company(
    media_company_id: str,
    body: MediaCompanyUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    미디어사 정보 수정.
    이름 변경 시 중복 체크.
    """
    mc = db.query(MediaCompany).filter(
        MediaCompany.id == media_company_id
    ).first()
    if not mc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="미디어사를 찾을 수 없습니다",
        )

    # 이름 변경 시 중복 체크
    if body.name and body.name != mc.name:
        dup = db.query(MediaCompany).filter(
            MediaCompany.name == body.name,
            MediaCompany.id != mc.id,
        ).first()
        if dup:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"이미 등록된 미디어사명입니다: {body.name}",
            )
        mc.name = body.name

    # 나머지 필드 업데이트 (None이면 변경 안 함)
    if body.contact_email is not None:
        mc.contact_email = body.contact_email
    if body.contact_phone is not None:
        mc.contact_phone = body.contact_phone
    if body.bank_account is not None:
        mc.bank_account = body.bank_account
    if body.is_active is not None:
        mc.is_active = body.is_active

    db.commit()
    db.refresh(mc)

    stats = _calc_media_stats(mc, db)
    return MediaCompanyResponse(
        id=str(mc.id),
        name=mc.name,
        contact_email=mc.contact_email,
        contact_phone=mc.contact_phone,
        bank_account=mc.bank_account,
        is_active=mc.is_active,
        **stats,
    )


# ============================
# 미디어사 소프트 삭제
# ============================

@router.delete(
    "/media-companies/{media_company_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="미디어사 삭제 (어드민)",
)
async def delete_media_company(
    media_company_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    미디어사 소프트 삭제 (is_active=False).

    진행 중인 주문(IN_PROGRESS)이 배정된 경우 삭제 불가.
    """
    mc = db.query(MediaCompany).filter(
        MediaCompany.id == media_company_id
    ).first()
    if not mc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="미디어사를 찾을 수 없습니다",
        )

    # 진행 중인 주문 여부 확인
    in_progress_count = db.query(func.count(Order.id)).filter(
        Order.media_company_id == mc.id,
        Order.status == OrderStatus.IN_PROGRESS,
    ).scalar() or 0

    if in_progress_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="진행 중인 주문이 있는 미디어사는 삭제할 수 없습니다.",
        )

    mc.is_active = False
    db.commit()


# =====================
# 미구현 엔드포인트 (Sprint 9 예정)
# =====================

@router.get("/users", summary="유저 목록 (Sprint 9 예정)")
async def list_users(admin: User = Depends(require_admin)):
    """유저 관리 — Sprint 9에서 구현 예정"""
    raise HTTPException(status_code=501, detail="Sprint 9에서 구현 예정")


@router.patch("/users/{user_id}/suspend", summary="유저 정지 (Sprint 9 예정)")
async def suspend_user(user_id: str, admin: User = Depends(require_admin)):
    """유저 정지 — Sprint 9에서 구현 예정"""
    raise HTTPException(status_code=501, detail="Sprint 9에서 구현 예정")
