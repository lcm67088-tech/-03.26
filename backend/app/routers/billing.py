"""
빌링 라우터
Sprint 8: 구독 관리 + 결제 내역 + 플랜 업/다운그레이드 + 결제 수단

엔드포인트 목록:
  GET  /billing/subscription        - 현재 구독 조회 (플랜 한도 + 사용량 포함)
  GET  /billing/history             - 결제 내역 목록 (페이지네이션)
  POST /billing/upgrade             - 플랜 업그레이드
  POST /billing/downgrade           - 플랜 다운그레이드 (초과 장소/키워드 비활성화)
  POST /billing/cancel              - 구독 취소
  GET  /billing/payment-method      - 결제 수단 조회
  POST /billing/payment-method      - 결제 수단 등록/변경
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.constants import (
    PLAN_LIMITS,
    PLAN_PRICES,
    get_plan_limits,
    get_plan_price,
    get_plan_rank,
)
from app.core.dependencies import get_current_user, get_db, get_workspace
from app.models.keyword import PlaceKeyword
from app.models.notification import NotificationType
from app.models.order import Order
from app.models.place import Place
from app.models.subscription import BillingHistory, Subscription
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.billing import (
    BillingHistoryListResponse,
    BillingHistoryResponse,
    CancelSubscriptionRequest,
    PaymentMethodRequest,
    PaymentMethodResponse,
    PlanUpgradeRequest,
    PlanUpgradeResponse,
    SubscriptionResponse,
    SubscriptionWithLimitsResponse,
)
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ─────────────────────────────────────────────────────────────
# 내부 헬퍼 함수
# ─────────────────────────────────────────────────────────────

def _get_active_subscription(
    db: Session,
    workspace_id: UUID,
) -> Optional[Subscription]:
    """워크스페이스의 활성 구독을 반환합니다. 없으면 None."""
    return (
        db.query(Subscription)
        .filter(
            Subscription.workspace_id == workspace_id,
            Subscription.status == "active",
        )
        .order_by(Subscription.created_at.desc())
        .first()
    )


def _get_or_create_subscription(
    db: Session,
    workspace: Workspace,
) -> Subscription:
    """
    활성 구독을 조회합니다.
    없으면 현재 워크스페이스 플랜 기반 free 구독을 생성하여 반환합니다.
    """
    sub = _get_active_subscription(db, workspace.id)
    if sub:
        return sub

    # free 기본 구독 생성
    sub = Subscription(
        workspace_id=workspace.id,
        plan=workspace.plan.value if hasattr(workspace.plan, "value") else str(workspace.plan),
        billing_cycle="monthly",
        status="active",
        amount=0,
        started_at=datetime.utcnow(),
    )
    db.add(sub)
    db.flush()
    return sub


def _count_workspace_places(db: Session, workspace_id: UUID) -> int:
    """워크스페이스의 활성 장소 수를 반환합니다."""
    return (
        db.query(Place)
        .filter(
            Place.workspace_id == workspace_id,
            Place.is_active == True,
        )
        .count()
    )


def _count_workspace_keywords(db: Session, workspace_id: UUID) -> int:
    """워크스페이스의 모든 활성 키워드 수를 반환합니다."""
    return (
        db.query(PlaceKeyword)
        .join(Place, PlaceKeyword.place_id == Place.id)
        .filter(
            Place.workspace_id == workspace_id,
            PlaceKeyword.is_active == True,
        )
        .count()
    )


def _subscription_to_response(sub: Subscription) -> SubscriptionResponse:
    """Subscription ORM → SubscriptionResponse 변환"""
    return SubscriptionResponse(
        id=sub.id,
        workspace_id=sub.workspace_id,
        plan=sub.plan,
        billing_cycle=sub.billing_cycle,
        status=sub.status,
        amount=sub.amount,
        started_at=sub.started_at,
        next_billing_at=sub.next_billing_at,
        cancelled_at=sub.cancelled_at,
        created_at=sub.created_at,
        updated_at=sub.updated_at,
    )


def _history_to_response(h: BillingHistory) -> BillingHistoryResponse:
    """BillingHistory ORM → BillingHistoryResponse 변환"""
    return BillingHistoryResponse(
        id=h.id,
        workspace_id=h.workspace_id,
        subscription_id=h.subscription_id,
        type=h.type,
        plan=h.plan,
        billing_cycle=h.billing_cycle,
        amount=h.amount,
        status=h.status,
        pg_transaction_id=h.pg_transaction_id,
        description=h.description,
        created_at=h.created_at,
    )


def _make_next_billing_at(billing_cycle: str) -> datetime:
    """결제 주기에 따른 다음 결제일 계산 (오늘 기준)"""
    now = datetime.utcnow()
    if billing_cycle == "yearly":
        return now + timedelta(days=365)
    return now + timedelta(days=30)


# ─────────────────────────────────────────────────────────────
# GET /billing/subscription
# ─────────────────────────────────────────────────────────────

@router.get(
    "/billing/subscription",
    response_model=SubscriptionWithLimitsResponse,
    summary="현재 구독 조회",
    description="현재 워크스페이스의 활성 구독 정보 + 플랜 한도 + 현재 사용량을 반환합니다.",
)
def get_subscription(
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_workspace),
    db: Session = Depends(get_db),
):
    """현재 구독 조회 (플랜 한도 + 현재 사용량 포함)"""

    sub = _get_or_create_subscription(db, workspace)
    plan_str = sub.plan
    limits = get_plan_limits(plan_str)
    prices = PLAN_PRICES.get(plan_str, {"monthly": 0, "yearly": 0})

    # 현재 사용량 집계
    current_places = _count_workspace_places(db, workspace.id)
    current_keywords = _count_workspace_keywords(db, workspace.id)

    db.commit()

    return SubscriptionWithLimitsResponse(
        id=sub.id,
        workspace_id=sub.workspace_id,
        plan=plan_str,
        billing_cycle=sub.billing_cycle,
        status=sub.status,
        amount=sub.amount,
        started_at=sub.started_at,
        next_billing_at=sub.next_billing_at,
        cancelled_at=sub.cancelled_at,
        created_at=sub.created_at,
        updated_at=sub.updated_at,
        plan_limits=limits,
        plan_price_monthly=prices["monthly"],
        plan_price_yearly=prices["yearly"],
        current_places=current_places,
        current_keywords=current_keywords,
    )


# ─────────────────────────────────────────────────────────────
# GET /billing/history
# ─────────────────────────────────────────────────────────────

@router.get(
    "/billing/history",
    response_model=BillingHistoryListResponse,
    summary="결제 내역 목록 조회",
    description="현재 워크스페이스의 결제/플랜 변경 내역을 최신순으로 반환합니다.",
)
def get_billing_history(
    page: int = Query(default=1, ge=1, description="페이지 번호"),
    limit: int = Query(default=20, ge=1, le=100, description="페이지당 항목 수"),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_workspace),
    db: Session = Depends(get_db),
):
    """결제 내역 목록 (페이지네이션)"""

    total = (
        db.query(BillingHistory)
        .filter(BillingHistory.workspace_id == workspace.id)
        .count()
    )
    items = (
        db.query(BillingHistory)
        .filter(BillingHistory.workspace_id == workspace.id)
        .order_by(BillingHistory.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return BillingHistoryListResponse(
        items=[_history_to_response(h) for h in items],
        total=total,
        page=page,
        limit=limit,
    )


# ─────────────────────────────────────────────────────────────
# POST /billing/upgrade
# ─────────────────────────────────────────────────────────────

@router.post(
    "/billing/upgrade",
    response_model=PlanUpgradeResponse,
    status_code=200,
    summary="플랜 업그레이드",
    description="현재 플랜보다 상위 플랜으로 업그레이드합니다. Mock PG 결제 처리.",
)
async def upgrade_plan(
    body: PlanUpgradeRequest,
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_workspace),
    db: Session = Depends(get_db),
):
    """플랜 업그레이드 (Mock PG 결제)"""

    # 현재 플랜 확인
    current_plan = workspace.plan.value if hasattr(workspace.plan, "value") else str(workspace.plan)
    target_plan = body.plan

    current_rank = get_plan_rank(current_plan)
    target_rank = get_plan_rank(target_plan)

    # 동일 플랜 체크
    if current_plan == target_plan:
        raise HTTPException(
            status_code=400,
            detail="현재 이미 해당 플랜을 사용 중입니다.",
        )

    # 다운그레이드 요청 방지
    if target_rank < current_rank:
        raise HTTPException(
            status_code=400,
            detail="업그레이드만 가능합니다. 다운그레이드는 /billing/downgrade를 사용하세요.",
        )

    # 결제 금액 계산
    amount = get_plan_price(target_plan, body.billing_cycle)

    # Mock PG 결제 트랜잭션 ID 생성
    timestamp = int(datetime.utcnow().timestamp())
    pg_transaction_id = f"mock_upgrade_{timestamp}"

    # 기존 활성 구독 cancelled 처리
    existing_sub = _get_active_subscription(db, workspace.id)
    if existing_sub:
        existing_sub.status = "cancelled"
        existing_sub.cancelled_at = datetime.utcnow()

    # 새 구독 생성
    new_sub = Subscription(
        workspace_id=workspace.id,
        plan=target_plan,
        billing_cycle=body.billing_cycle,
        status="active",
        amount=amount,
        started_at=datetime.utcnow(),
        next_billing_at=_make_next_billing_at(body.billing_cycle),
    )
    db.add(new_sub)
    db.flush()

    # 결제 내역 생성
    description = (
        f"{current_plan.upper()} → {target_plan.upper()} 업그레이드 "
        f"({'연간' if body.billing_cycle == 'yearly' else '월간'})"
    )
    history = BillingHistory(
        workspace_id=workspace.id,
        subscription_id=new_sub.id,
        type="upgrade",
        plan=target_plan,
        billing_cycle=body.billing_cycle,
        amount=amount,
        status="paid",
        pg_transaction_id=pg_transaction_id,
        description=description,
        created_at=datetime.utcnow(),
    )
    db.add(history)

    # 워크스페이스 플랜 업데이트
    workspace.plan = target_plan

    db.flush()

    # 알림 발송 (비동기, 실패해도 진행)
    try:
        await notification_service.create_notification(
            db=db,
            user_id=current_user.id,
            notification_type=NotificationType.PLAN_UPGRADED,
            data={
                "old_plan": current_plan.upper(),
                "new_plan": target_plan.upper(),
            },
            workspace_id=workspace.id,
        )
    except Exception as e:
        logger.warning(f"플랜 업그레이드 알림 발송 실패: {e}")

    db.commit()
    db.refresh(new_sub)
    db.refresh(history)

    logger.info(
        f"[빌링] 플랜 업그레이드: workspace={workspace.id} "
        f"{current_plan}→{target_plan} pg={pg_transaction_id}"
    )

    return PlanUpgradeResponse(
        subscription=_subscription_to_response(new_sub),
        billing_history=_history_to_response(history),
        message=f"{target_plan.upper()} 플랜으로 업그레이드되었습니다.",
        deactivated_places=0,
        deactivated_keywords=0,
    )


# ─────────────────────────────────────────────────────────────
# POST /billing/downgrade
# ─────────────────────────────────────────────────────────────

@router.post(
    "/billing/downgrade",
    response_model=PlanUpgradeResponse,
    status_code=200,
    summary="플랜 다운그레이드",
    description=(
        "현재 플랜보다 하위 플랜으로 다운그레이드합니다. "
        "초과 장소/키워드는 최근 등록 순으로 비활성화됩니다."
    ),
)
async def downgrade_plan(
    body: PlanUpgradeRequest,
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_workspace),
    db: Session = Depends(get_db),
):
    """플랜 다운그레이드 (초과 장소/키워드 자동 비활성화)"""

    current_plan = workspace.plan.value if hasattr(workspace.plan, "value") else str(workspace.plan)
    target_plan = body.plan

    current_rank = get_plan_rank(current_plan)
    target_rank = get_plan_rank(target_plan)

    # 동일 플랜 체크
    if current_plan == target_plan:
        raise HTTPException(
            status_code=400,
            detail="현재 이미 해당 플랜을 사용 중입니다.",
        )

    # 업그레이드 요청 방지
    if target_rank > current_rank:
        raise HTTPException(
            status_code=400,
            detail="다운그레이드만 가능합니다. 업그레이드는 /billing/upgrade를 사용하세요.",
        )

    # 새 플랜 한도 조회
    new_limits = get_plan_limits(target_plan)
    max_places = new_limits["max_places"]
    max_keywords = new_limits["max_keywords"]

    # 초과 장소 비활성화 (최근 등록 순으로 초과분 비활성화)
    deactivated_places = 0
    places = (
        db.query(Place)
        .filter(
            Place.workspace_id == workspace.id,
            Place.is_active == True,
        )
        .order_by(Place.created_at.asc())  # 오래된 것부터 유지
        .all()
    )
    if len(places) > max_places:
        # 초과분 (뒤에서부터 = 최근 등록)을 비활성화
        places_to_deactivate = places[max_places:]
        for place in places_to_deactivate:
            place.is_active = False
            # 해당 장소의 키워드도 비활성화
            db.query(PlaceKeyword).filter(
                PlaceKeyword.place_id == place.id,
                PlaceKeyword.is_active == True,
            ).update({"is_active": False})
            deactivated_places += 1
        db.flush()

    # 초과 키워드 비활성화 (남은 활성 장소들의 키워드 대상)
    deactivated_keywords = 0
    if max_keywords < 999:  # enterprise(999)는 무제한으로 처리
        # 남은 활성 장소 ID 목록
        active_place_ids = [
            p.id for p in db.query(Place)
            .filter(Place.workspace_id == workspace.id, Place.is_active == True)
            .all()
        ]
        active_keywords = (
            db.query(PlaceKeyword)
            .filter(
                PlaceKeyword.place_id.in_(active_place_ids),
                PlaceKeyword.is_active == True,
            )
            .order_by(PlaceKeyword.created_at.asc())  # 오래된 것부터 유지
            .all()
        )
        if len(active_keywords) > max_keywords:
            keywords_to_deactivate = active_keywords[max_keywords:]
            for kw in keywords_to_deactivate:
                kw.is_active = False
                deactivated_keywords += 1
            db.flush()

    # 결제 금액 (무료로 다운그레이드 시 0)
    amount = get_plan_price(target_plan, body.billing_cycle)

    # Mock PG 트랜잭션 ID
    timestamp = int(datetime.utcnow().timestamp())
    pg_transaction_id = f"mock_downgrade_{timestamp}" if amount > 0 else None

    # 기존 활성 구독 cancelled 처리
    existing_sub = _get_active_subscription(db, workspace.id)
    if existing_sub:
        existing_sub.status = "cancelled"
        existing_sub.cancelled_at = datetime.utcnow()

    # 새 구독 생성 (free는 next_billing_at 없음)
    new_sub = Subscription(
        workspace_id=workspace.id,
        plan=target_plan,
        billing_cycle=body.billing_cycle,
        status="active",
        amount=amount,
        started_at=datetime.utcnow(),
        next_billing_at=_make_next_billing_at(body.billing_cycle) if amount > 0 else None,
    )
    db.add(new_sub)
    db.flush()

    # 결제 내역 생성
    desc_parts = [f"{current_plan.upper()} → {target_plan.upper()} 다운그레이드"]
    if deactivated_places > 0:
        desc_parts.append(f"장소 {deactivated_places}개 비활성화")
    if deactivated_keywords > 0:
        desc_parts.append(f"키워드 {deactivated_keywords}개 비활성화")
    description = " / ".join(desc_parts)

    history = BillingHistory(
        workspace_id=workspace.id,
        subscription_id=new_sub.id,
        type="downgrade",
        plan=target_plan,
        billing_cycle=body.billing_cycle,
        amount=0,          # 다운그레이드는 환불/비과금 처리 → 0
        status="paid",
        pg_transaction_id=pg_transaction_id,
        description=description,
        created_at=datetime.utcnow(),
    )
    db.add(history)

    # 워크스페이스 플랜 업데이트
    workspace.plan = target_plan

    db.flush()

    # 알림 발송
    try:
        await notification_service.create_notification(
            db=db,
            user_id=current_user.id,
            notification_type=NotificationType.PLAN_DOWNGRADED,
            data={
                "old_plan": current_plan.upper(),
                "new_plan": target_plan.upper(),
            },
            workspace_id=workspace.id,
        )
    except Exception as e:
        logger.warning(f"플랜 다운그레이드 알림 발송 실패: {e}")

    db.commit()
    db.refresh(new_sub)
    db.refresh(history)

    logger.info(
        f"[빌링] 플랜 다운그레이드: workspace={workspace.id} "
        f"{current_plan}→{target_plan} "
        f"비활성화: 장소={deactivated_places} 키워드={deactivated_keywords}"
    )

    return PlanUpgradeResponse(
        subscription=_subscription_to_response(new_sub),
        billing_history=_history_to_response(history),
        message=(
            f"{target_plan.upper()} 플랜으로 변경되었습니다."
            + (f" (장소 {deactivated_places}개, 키워드 {deactivated_keywords}개 비활성화)" if deactivated_places or deactivated_keywords else "")
        ),
        deactivated_places=deactivated_places,
        deactivated_keywords=deactivated_keywords,
    )


# ─────────────────────────────────────────────────────────────
# POST /billing/cancel
# ─────────────────────────────────────────────────────────────

@router.post(
    "/billing/cancel",
    summary="구독 취소",
    description="현재 구독을 취소합니다. next_billing_at까지 현재 플랜을 유지합니다.",
)
def cancel_subscription(
    body: CancelSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_workspace),
    db: Session = Depends(get_db),
):
    """구독 취소 (next_billing_at까지 현재 플랜 유지)"""

    current_plan = workspace.plan.value if hasattr(workspace.plan, "value") else str(workspace.plan)

    # free 플랜은 취소할 구독 없음
    if current_plan == "free":
        raise HTTPException(
            status_code=400,
            detail="취소할 구독이 없습니다.",
        )

    sub = _get_active_subscription(db, workspace.id)
    if not sub:
        raise HTTPException(
            status_code=400,
            detail="취소할 구독이 없습니다.",
        )

    # 구독 취소 처리 (next_billing_at까지 유지)
    sub.status = "cancelled"
    sub.cancelled_at = datetime.utcnow()

    # 취소 이력 생성
    history = BillingHistory(
        workspace_id=workspace.id,
        subscription_id=sub.id,
        type="downgrade",
        plan=current_plan,
        billing_cycle=sub.billing_cycle,
        amount=0,
        status="paid",
        description=f"구독 취소{' - ' + body.reason if body.reason else ''}",
        created_at=datetime.utcnow(),
    )
    db.add(history)
    db.commit()

    # 만료일 포맷팅
    expire_str = ""
    if sub.next_billing_at:
        expire_str = sub.next_billing_at.strftime("%Y년 %m월 %d일")
    else:
        expire_str = "즉시"

    logger.info(
        f"[빌링] 구독 취소: workspace={workspace.id} plan={current_plan} "
        f"만료={expire_str}"
    )

    return {
        "message": f"구독이 취소되었습니다. 현재 플랜은 {expire_str}까지 유지됩니다.",
        "cancelled_at": sub.cancelled_at.isoformat(),
        "expires_at": sub.next_billing_at.isoformat() if sub.next_billing_at else None,
    }


# ─────────────────────────────────────────────────────────────
# GET /billing/payment-method
# ─────────────────────────────────────────────────────────────

@router.get(
    "/billing/payment-method",
    summary="결제 수단 조회",
    description="현재 워크스페이스에 등록된 결제 수단(카드)을 조회합니다.",
)
def get_payment_method(
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_workspace),
    db: Session = Depends(get_db),
):
    """결제 수단 조회 (없으면 null)"""

    if not workspace.payment_method:
        return {"payment_method": None}

    pm = workspace.payment_method
    response = PaymentMethodResponse(
        card_number_last4=pm.get("card_number_last4", ""),
        card_brand=pm.get("card_brand", ""),
        exp_month=pm.get("exp_month", ""),
        exp_year=pm.get("exp_year", ""),
        pg_customer_id=pm.get("pg_customer_id"),
    )
    return {"payment_method": response.model_dump()}


# ─────────────────────────────────────────────────────────────
# POST /billing/payment-method
# ─────────────────────────────────────────────────────────────

@router.post(
    "/billing/payment-method",
    summary="결제 수단 등록/변경",
    description="카드 정보를 등록하거나 변경합니다. Mock 처리 (실제 PG 연동은 Sprint 10).",
)
def update_payment_method(
    body: PaymentMethodRequest,
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_workspace),
    db: Session = Depends(get_db),
):
    """결제 수단 등록/변경 (Mock PG)"""

    # Mock PG customer ID 생성 (없는 경우)
    pg_customer_id = body.pg_customer_id
    if not pg_customer_id:
        timestamp = int(datetime.utcnow().timestamp())
        pg_customer_id = f"mock_cust_{workspace.id}_{timestamp}"

    # workspace.payment_method 저장
    workspace.payment_method = {
        "card_number_last4": body.card_number_last4,
        "card_brand": body.card_brand,
        "exp_month": body.exp_month,
        "exp_year": body.exp_year,
        "pg_customer_id": pg_customer_id,
    }
    db.commit()

    response = PaymentMethodResponse(
        card_number_last4=body.card_number_last4,
        card_brand=body.card_brand,
        exp_month=body.exp_month,
        exp_year=body.exp_year,
        pg_customer_id=pg_customer_id,
    )

    logger.info(
        f"[빌링] 결제 수단 등록: workspace={workspace.id} "
        f"card=**** {body.card_number_last4} brand={body.card_brand}"
    )

    return {
        "message": "결제 수단이 등록되었습니다.",
        "payment_method": response.model_dump(),
    }
