"""
어드민 통계 라우터 (Sprint 9)

엔드포인트 목록:
  GET  /admin/stats/overview        KPI 통계 (MRR, ARR, 신규 유저 등)
  GET  /admin/stats/revenue         월별 매출 통계 (최근 N개월)
  GET  /admin/stats/export/csv      통계 데이터 CSV 내보내기

계산 로직:
  MRR = 이번 달 paid BillingHistory 합산
  ARR = MRR × 12
  plan_distribution = 활성 워크스페이스 플랜별 카운트
"""

import csv
import io
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.order import Order, OrderStatus
from app.models.subscription import BillingHistory
from app.models.user import User
from app.models.workspace import Workspace, WorkspacePlan
from app.schemas.admin_advanced import (
    MonthlyRevenueStat,
    MonthlyRevenueResponse,
    PlanDistributionStat,
    StatsOverview,
)

router = APIRouter(prefix="/admin/stats", tags=["어드민-통계"])


# ============================================================
# Helper: 날짜 범위 내 paid BillingHistory 합산
# ============================================================

def _sum_revenue(db: Session, start: datetime, end: datetime) -> int:
    """특정 기간 내 paid BillingHistory 합산"""
    result = db.query(func.coalesce(func.sum(BillingHistory.amount), 0)).filter(
        BillingHistory.status == "paid",
        BillingHistory.created_at >= start,
        BillingHistory.created_at < end,
    ).scalar()
    return int(result or 0)


def _count_orders(db: Session, start: datetime, end: datetime) -> int:
    """특정 기간 내 주문 수"""
    return db.query(func.count(Order.id)).filter(
        Order.created_at >= start,
        Order.created_at < end,
    ).scalar() or 0


def _count_new_users(db: Session, start: datetime, end: datetime) -> int:
    """특정 기간 내 신규 유저 수"""
    return db.query(func.count(User.id)).filter(
        User.created_at >= start,
        User.created_at < end,
    ).scalar() or 0


# ============================================================
# GET /admin/stats/overview — KPI 통계
# ============================================================

@router.get("/overview", response_model=StatsOverview, summary="어드민 KPI 통계 조회")
async def get_stats_overview(
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StatsOverview:
    """
    대시보드 KPI 통계를 반환합니다.
    - 오늘 주문/매출
    - 이번 달 신규 유저/워크스페이스
    - MRR / ARR
    - 전체/활성 워크스페이스 수
    - 플랜 분포
    """
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    today_end = today_start + timedelta(days=1)
    month_start = datetime(now.year, now.month, 1)

    # 오늘 주문 수
    today_orders = _count_orders(db, today_start, today_end)

    # 오늘 매출 (paid BillingHistory)
    today_revenue = _sum_revenue(db, today_start, today_end)

    # 이번 달 신규 유저
    month_new_users = _count_new_users(db, month_start, today_end)

    # 이번 달 신규 워크스페이스
    month_new_workspaces = db.query(func.count(Workspace.id)).filter(
        Workspace.created_at >= month_start,
        Workspace.created_at < today_end,
    ).scalar() or 0

    # MRR = 이번 달 paid BillingHistory 합산
    mrr = _sum_revenue(db, month_start, today_end)

    # ARR = MRR × 12
    arr = mrr * 12

    # 전체 유저/워크스페이스
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_workspaces = db.query(func.count(Workspace.id)).scalar() or 0
    active_workspaces = db.query(func.count(Workspace.id)).filter(
        Workspace.is_active == True
    ).scalar() or 0

    # 전체 주문 수
    total_orders = db.query(func.count(Order.id)).scalar() or 0

    # 대기 중 주문 수 (pending/confirmed)
    pending_orders = db.query(func.count(Order.id)).filter(
        Order.status.in_([OrderStatus.PENDING, OrderStatus.CONFIRMED])
    ).scalar() or 0

    # 플랜별 분포 (활성 워크스페이스만)
    plan_rows = db.query(
        Workspace.plan, func.count(Workspace.id)
    ).filter(
        Workspace.is_active == True
    ).group_by(Workspace.plan).all()

    plan_dist = PlanDistributionStat()
    for plan, cnt in plan_rows:
        plan_val = plan.value if hasattr(plan, "value") else str(plan)
        if plan_val == "free":
            plan_dist.free = cnt
        elif plan_val == "starter":
            plan_dist.starter = cnt
        elif plan_val == "pro":
            plan_dist.pro = cnt
        elif plan_val == "enterprise":
            plan_dist.enterprise = cnt

    return StatsOverview(
        today_orders=today_orders,
        today_revenue=today_revenue,
        month_new_users=month_new_users,
        month_new_workspaces=month_new_workspaces,
        mrr=mrr,
        arr=arr,
        total_users=total_users,
        total_workspaces=total_workspaces,
        active_workspaces=active_workspaces,
        total_orders=total_orders,
        pending_orders=pending_orders,
        plan_distribution=plan_dist,
    )


# ============================================================
# GET /admin/stats/revenue — 월별 매출 통계
# ============================================================

@router.get("/revenue", response_model=MonthlyRevenueResponse, summary="월별 매출 통계 조회")
async def get_monthly_revenue(
    months: int = Query(6, ge=1, le=24, description="조회할 최근 개월 수"),
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MonthlyRevenueResponse:
    """
    최근 N개월의 월별 매출 통계를 반환합니다.
    - revenue: 해당 월 paid BillingHistory 합산
    - order_count: 해당 월 주문 수
    - new_users: 해당 월 신규 유저 수
    """
    now = datetime.utcnow()
    items = []

    for i in range(months - 1, -1, -1):
        # i개월 전 월 계산
        # 현재 월 기준으로 i개월 전
        year = now.year
        month = now.month - i
        while month <= 0:
            month += 12
            year -= 1

        import calendar
        last_day = calendar.monthrange(year, month)[1]
        start = datetime(year, month, 1)
        end = datetime(year, month, last_day, 23, 59, 59)
        end_exclusive = datetime(year, month, last_day) + timedelta(days=1)

        revenue = _sum_revenue(db, start, end_exclusive)
        order_count = _count_orders(db, start, end_exclusive)
        new_users = _count_new_users(db, start, end_exclusive)

        items.append(MonthlyRevenueStat(
            month=f"{year:04d}-{month:02d}",
            revenue=revenue,
            order_count=order_count,
            new_users=new_users,
        ))

    return MonthlyRevenueResponse(items=items)


# ============================================================
# GET /admin/stats/export/csv — 통계 CSV 내보내기
# ============================================================

@router.get("/export/csv", summary="월별 통계 CSV 내보내기")
async def export_stats_csv(
    months: int = Query(12, ge=1, le=24),
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """최근 N개월 통계를 CSV로 내보냅니다."""
    now = datetime.utcnow()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "월", "매출(원)", "주문수", "신규유저수",
    ])

    for i in range(months - 1, -1, -1):
        year = now.year
        month = now.month - i
        while month <= 0:
            month += 12
            year -= 1

        import calendar
        last_day = calendar.monthrange(year, month)[1]
        start = datetime(year, month, 1)
        end_exclusive = datetime(year, month, last_day) + timedelta(days=1)

        revenue = _sum_revenue(db, start, end_exclusive)
        order_count = _count_orders(db, start, end_exclusive)
        new_users = _count_new_users(db, start, end_exclusive)

        writer.writerow([
            f"{year:04d}-{month:02d}",
            revenue,
            order_count,
            new_users,
        ])

    output.seek(0)
    today = datetime.utcnow().strftime("%Y%m%d")
    filename = f"export_stats_{today}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
