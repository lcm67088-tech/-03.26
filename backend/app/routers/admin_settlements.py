"""
어드민 정산 관리 라우터 (Sprint 9)

엔드포인트 목록:
  GET    /admin/settlements               정산 목록 (필터·페이지네이션)
  GET    /admin/settlements/{id}          정산 상세
  POST   /admin/settlements/generate      정산 생성 (월별 완료 주문 집계)
  POST   /admin/settlements/{id}/approve  정산 승인
  POST   /admin/settlements/{id}/pay      지급 처리
  GET    /admin/settlements/export/csv    CSV 내보내기

비즈니스 규칙:
  - generate: 해당 미디어사 + 월 중복 방지 (UniqueConstraint)
  - generate: completed 상태 주문만 집계
  - commission_amount = round(total_amount * commission_rate)
  - approve: pending → approved 전환
  - pay: approved → paid 전환
"""

import csv
import io
import uuid as uuid_lib
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.media_company import MediaCompany
from app.models.order import Order, OrderStatus
from app.models.settlement import Settlement, SettlementItem
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.admin_advanced import (
    SettlementApproveReq,
    SettlementDetail,
    SettlementGenerateReq,
    SettlementItemSchema,
    SettlementListItem,
    SettlementListResponse,
)

router = APIRouter(prefix="/admin/settlements", tags=["어드민-정산관리"])


# ============================================================
# Helper: Settlement → SettlementListItem 변환
# ============================================================

def _build_settlement_list_item(s: Settlement, db: Session) -> SettlementListItem:
    mc = db.query(MediaCompany).filter(MediaCompany.id == s.media_company_id).first()
    return SettlementListItem(
        id=str(s.id),
        media_company_id=str(s.media_company_id),
        media_company_name=mc.name if mc else "",
        month=s.month,
        status=s.status,
        total_orders=s.total_orders,
        total_amount=s.total_amount,
        commission_rate=s.commission_rate,
        commission_amount=s.commission_amount,
        approved_at=s.approved_at,
        paid_at=s.paid_at,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


# ============================================================
# GET /admin/settlements — 정산 목록
# ============================================================

@router.get("", response_model=SettlementListResponse, summary="정산 목록 조회")
async def list_settlements(
    month: Optional[str] = Query(None, description="정산 월 필터 (YYYY-MM)"),
    media_company_id: Optional[str] = Query(None, description="미디어사 UUID 필터"),
    settlement_status: Optional[str] = Query(None, alias="status", description="상태 필터 (pending/approved/paid)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SettlementListResponse:
    """정산 목록을 필터·페이지네이션으로 조회합니다."""
    query = db.query(Settlement)

    if month:
        query = query.filter(Settlement.month == month)
    if media_company_id:
        query = query.filter(Settlement.media_company_id == media_company_id)
    if settlement_status:
        query = query.filter(Settlement.status == settlement_status)

    query = query.order_by(Settlement.created_at.desc())
    total = query.count()
    settlements = query.offset(skip).limit(limit).all()

    items = [_build_settlement_list_item(s, db) for s in settlements]
    return SettlementListResponse(total=total, items=items)


# ============================================================
# GET /admin/settlements/export/csv — CSV 내보내기
# ============================================================

@router.get("/export/csv", summary="정산 목록 CSV 내보내기")
async def export_settlements_csv(
    month: Optional[str] = Query(None),
    media_company_id: Optional[str] = Query(None),
    settlement_status: Optional[str] = Query(None, alias="status"),
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """정산 전체 목록을 CSV로 내보냅니다."""
    query = db.query(Settlement)
    if month:
        query = query.filter(Settlement.month == month)
    if media_company_id:
        query = query.filter(Settlement.media_company_id == media_company_id)
    if settlement_status:
        query = query.filter(Settlement.status == settlement_status)

    query = query.order_by(Settlement.created_at.desc())
    settlements = query.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "정산ID", "미디어사ID", "미디어사명", "정산월", "상태",
        "총주문수", "총금액", "수수료율", "지급액",
        "승인일시", "지급일시", "생성일시",
    ])
    for s in settlements:
        mc = db.query(MediaCompany).filter(MediaCompany.id == s.media_company_id).first()
        writer.writerow([
            str(s.id),
            str(s.media_company_id),
            mc.name if mc else "",
            s.month,
            s.status,
            s.total_orders,
            s.total_amount,
            s.commission_rate,
            s.commission_amount,
            s.approved_at.isoformat() if s.approved_at else "",
            s.paid_at.isoformat() if s.paid_at else "",
            s.created_at.isoformat() if s.created_at else "",
        ])

    output.seek(0)
    today = datetime.utcnow().strftime("%Y%m%d")
    filename = f"export_settlements_{today}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ============================================================
# GET /admin/settlements/{settlement_id} — 정산 상세
# ============================================================

@router.get("/{settlement_id}", response_model=SettlementDetail, summary="정산 상세 조회")
async def get_settlement(
    settlement_id: UUID,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SettlementDetail:
    """정산 상세 정보 (항목 목록 포함)를 반환합니다."""
    s = db.query(Settlement).filter(Settlement.id == settlement_id).first()
    if not s:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="정산을 찾을 수 없습니다",
        )

    mc = db.query(MediaCompany).filter(MediaCompany.id == s.media_company_id).first()

    # 정산 항목 목록
    items_orm = db.query(SettlementItem).filter(
        SettlementItem.settlement_id == s.id
    ).order_by(SettlementItem.created_at.desc()).all()

    items = []
    for si in items_orm:
        order = db.query(Order).filter(Order.id == si.order_id).first()
        ws_name = ""
        if order:
            ws = db.query(Workspace).filter(Workspace.id == order.workspace_id).first()
            ws_name = ws.name if ws else ""
        items.append(SettlementItemSchema(
            id=str(si.id),
            order_id=str(si.order_id),
            amount=si.amount,
            commission_amount=si.commission_amount,
            product_name=order.product_name if order else None,
            workspace_name=ws_name,
            ordered_at=order.ordered_at if order else None,
            created_at=si.created_at,
        ))

    return SettlementDetail(
        id=str(s.id),
        media_company_id=str(s.media_company_id),
        media_company_name=mc.name if mc else "",
        month=s.month,
        status=s.status,
        total_orders=s.total_orders,
        total_amount=s.total_amount,
        commission_rate=s.commission_rate,
        commission_amount=s.commission_amount,
        items=items,
        approved_at=s.approved_at,
        paid_at=s.paid_at,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


# ============================================================
# POST /admin/settlements/generate — 정산 생성
# ============================================================

@router.post(
    "/generate",
    response_model=SettlementDetail,
    status_code=status.HTTP_201_CREATED,
    summary="정산 생성 (완료 주문 집계)",
)
async def generate_settlement(
    body: SettlementGenerateReq,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SettlementDetail:
    """
    미디어사 + 월 기준으로 정산을 생성합니다.

    - 해당 월 completed 상태 주문을 집계
    - 이미 정산이 존재하면 409 Conflict
    - commission_amount = round(total_amount * commission_rate)
    """
    # 미디어사 존재 확인
    mc = db.query(MediaCompany).filter(
        MediaCompany.id == body.media_company_id,
        MediaCompany.is_active == True,
    ).first()
    if not mc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="미디어사를 찾을 수 없습니다",
        )

    # 중복 정산 방지
    existing = db.query(Settlement).filter(
        Settlement.media_company_id == body.media_company_id,
        Settlement.month == body.month,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{body.month} 정산이 이미 존재합니다 (상태: {existing.status})",
        )

    # 해당 월 completed 주문 집계
    # month: "YYYY-MM" → year/month 파싱
    try:
        year, mon = map(int, body.month.split("-"))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="월 형식이 올바르지 않습니다 (YYYY-MM)",
        )

    import calendar
    last_day = calendar.monthrange(year, mon)[1]
    month_start = datetime(year, mon, 1)
    month_end = datetime(year, mon, last_day, 23, 59, 59)

    completed_orders = db.query(Order).filter(
        Order.media_company_id == body.media_company_id,
        Order.status == OrderStatus.COMPLETED,
        Order.completed_at >= month_start,
        Order.completed_at <= month_end,
    ).all()

    # 이미 다른 정산에 포함된 주문 제외
    existing_order_ids = db.query(SettlementItem.order_id).all()
    existing_order_id_set = {str(r[0]) for r in existing_order_ids}
    eligible_orders = [o for o in completed_orders if str(o.id) not in existing_order_id_set]

    if not eligible_orders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{body.month} 동안 정산 가능한 완료 주문이 없습니다",
        )

    # 집계
    total_amount = sum(o.total_amount or 0 for o in eligible_orders)
    commission_amount = round(total_amount * body.commission_rate)

    # Settlement 헤더 생성
    settlement = Settlement(
        id=uuid_lib.uuid4(),
        media_company_id=body.media_company_id,
        month=body.month,
        status="pending",
        total_orders=len(eligible_orders),
        total_amount=total_amount,
        commission_rate=body.commission_rate,
        commission_amount=commission_amount,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(settlement)
    db.flush()  # settlement.id 확보

    # SettlementItem 생성
    items_orm = []
    for order in eligible_orders:
        item_commission = round((order.total_amount or 0) * body.commission_rate)
        si = SettlementItem(
            id=uuid_lib.uuid4(),
            settlement_id=settlement.id,
            order_id=order.id,
            amount=order.total_amount or 0,
            commission_amount=item_commission,
            created_at=datetime.utcnow(),
        )
        db.add(si)
        items_orm.append(si)

    db.commit()
    db.refresh(settlement)

    # 응답 빌드
    items = []
    for si in items_orm:
        order = next((o for o in eligible_orders if o.id == si.order_id), None)
        ws_name = ""
        if order:
            ws = db.query(Workspace).filter(Workspace.id == order.workspace_id).first()
            ws_name = ws.name if ws else ""
        items.append(SettlementItemSchema(
            id=str(si.id),
            order_id=str(si.order_id),
            amount=si.amount,
            commission_amount=si.commission_amount,
            product_name=order.product_name if order else None,
            workspace_name=ws_name,
            ordered_at=order.ordered_at if order else None,
            created_at=si.created_at,
        ))

    return SettlementDetail(
        id=str(settlement.id),
        media_company_id=str(settlement.media_company_id),
        media_company_name=mc.name,
        month=settlement.month,
        status=settlement.status,
        total_orders=settlement.total_orders,
        total_amount=settlement.total_amount,
        commission_rate=settlement.commission_rate,
        commission_amount=settlement.commission_amount,
        items=items,
        approved_at=settlement.approved_at,
        paid_at=settlement.paid_at,
        created_at=settlement.created_at,
        updated_at=settlement.updated_at,
    )


# ============================================================
# POST /admin/settlements/{settlement_id}/approve — 정산 승인
# ============================================================

@router.post(
    "/{settlement_id}/approve",
    summary="정산 승인 (pending → approved)",
)
async def approve_settlement(
    settlement_id: UUID,
    body: SettlementApproveReq,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    pending 상태의 정산을 approved로 변경합니다.
    """
    s = db.query(Settlement).filter(Settlement.id == settlement_id).first()
    if not s:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="정산을 찾을 수 없습니다",
        )

    if s.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"pending 상태의 정산만 승인할 수 있습니다 (현재: {s.status})",
        )

    s.status = "approved"
    s.approved_at = datetime.utcnow()
    s.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(s)

    mc = db.query(MediaCompany).filter(MediaCompany.id == s.media_company_id).first()
    return {
        "settlement_id": str(s.id),
        "media_company_name": mc.name if mc else "",
        "month": s.month,
        "status": s.status,
        "approved_at": s.approved_at.isoformat(),
        "note": body.note,
        "message": "정산이 승인되었습니다",
    }


# ============================================================
# POST /admin/settlements/{settlement_id}/pay — 지급 처리
# ============================================================

@router.post(
    "/{settlement_id}/pay",
    summary="정산 지급 처리 (approved → paid)",
)
async def pay_settlement(
    settlement_id: UUID,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    approved 상태의 정산을 paid로 변경합니다.
    """
    s = db.query(Settlement).filter(Settlement.id == settlement_id).first()
    if not s:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="정산을 찾을 수 없습니다",
        )

    if s.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"approved 상태의 정산만 지급 처리할 수 있습니다 (현재: {s.status})",
        )

    s.status = "paid"
    s.paid_at = datetime.utcnow()
    s.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(s)

    mc = db.query(MediaCompany).filter(MediaCompany.id == s.media_company_id).first()
    return {
        "settlement_id": str(s.id),
        "media_company_name": mc.name if mc else "",
        "month": s.month,
        "status": s.status,
        "commission_amount": s.commission_amount,
        "paid_at": s.paid_at.isoformat(),
        "message": f"{s.commission_amount:,}원이 지급 완료 처리되었습니다",
    }
