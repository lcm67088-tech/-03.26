"""
어드민 심화 전용 Pydantic 스키마 (Sprint 9 신규)

사용자 관리:
  AdminUserListItem       유저 목록 아이템
  AdminUserDetail         유저 상세 (워크스페이스·주문 포함)
  AdminUserRolePatch      역할 변경 요청
  AdminUserStatusPatch    활성/비활성 변경 요청

워크스페이스 관리:
  AdminWorkspaceListItem  워크스페이스 목록 아이템
  AdminWorkspaceDetail    워크스페이스 상세 (멤버·플레이스·빌링 포함)
  AdminWorkspacePlanPatch 플랜 변경 요청

정산 관리:
  SettlementListItem      정산 목록 아이템
  SettlementDetail        정산 상세 (항목 포함)
  SettlementGenerateReq   정산 생성 요청
  SettlementApproveReq    정산 승인 요청

통계:
  StatsOverview           대시보드 KPI 통계
  MonthlyRevenueStat      월별 매출 통계 아이템
  PlanDistributionStat    플랜별 분포
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================
# 유저 관리 스키마
# ============================================================

class AdminUserListItem(BaseModel):
    """어드민 유저 목록 아이템"""
    id: str
    email: str
    name: str
    phone: Optional[str] = None
    role: str                          # user / admin / superadmin
    is_active: bool
    email_verified: bool
    workspace_count: int = 0           # 오너 워크스페이스 수
    order_count: int = 0               # 전체 주문 수
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminUserListResponse(BaseModel):
    """유저 목록 페이지네이션 응답"""
    total: int
    items: List[AdminUserListItem]


class AdminUserWorkspaceSummary(BaseModel):
    """유저 상세에서 사용되는 워크스페이스 요약"""
    id: str
    name: str
    plan: str
    is_active: bool
    place_count: int = 0
    member_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminUserOrderSummary(BaseModel):
    """유저 상세에서 사용되는 최근 주문 요약"""
    id: str
    product_name: str
    status: str
    total_amount: int
    workspace_name: str
    ordered_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminUserDetail(BaseModel):
    """유저 상세 응답 (워크스페이스·최근 주문 포함)"""
    id: str
    email: str
    name: str
    phone: Optional[str] = None
    role: str
    is_active: bool
    email_verified: bool
    workspaces: List[AdminUserWorkspaceSummary] = []
    recent_orders: List[AdminUserOrderSummary] = []
    workspace_count: int = 0
    order_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminUserRolePatch(BaseModel):
    """유저 역할 변경 요청 (superadmin 전용)"""
    role: str = Field(
        description="변경할 역할 (user / admin / superadmin)",
        pattern="^(user|admin|superadmin)$",
    )
    reason: Optional[str] = Field(
        None,
        max_length=500,
        description="변경 사유 (감사 로그용)",
    )


class AdminUserStatusPatch(BaseModel):
    """유저 활성/비활성 변경 요청"""
    is_active: bool = Field(description="True=활성화, False=비활성화")
    reason: Optional[str] = Field(
        None,
        max_length=500,
        description="변경 사유",
    )


# ============================================================
# 워크스페이스 관리 스키마
# ============================================================

class AdminWorkspaceListItem(BaseModel):
    """어드민 워크스페이스 목록 아이템"""
    id: str
    name: str
    slug: str
    plan: str                          # free / starter / pro / enterprise
    is_active: bool
    owner_id: str
    owner_email: str
    owner_name: str
    member_count: int = 0
    place_count: int = 0
    order_count: int = 0
    monthly_spend: int = 0             # 이번 달 청구 금액
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminWorkspaceListResponse(BaseModel):
    """워크스페이스 목록 페이지네이션 응답"""
    total: int
    items: List[AdminWorkspaceListItem]


class AdminWorkspaceMemberSummary(BaseModel):
    """워크스페이스 상세에서 멤버 요약"""
    id: str
    user_id: str
    user_email: str
    user_name: str
    role: str
    joined_at: datetime

    model_config = {"from_attributes": True}


class AdminWorkspacePlaceSummary(BaseModel):
    """워크스페이스 상세에서 플레이스 요약"""
    id: str
    name: str
    alias: Optional[str] = None
    naver_place_id: str
    category: Optional[str] = None
    is_active: bool
    keyword_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminWorkspaceBillingItem(BaseModel):
    """워크스페이스 상세에서 청구 내역 요약"""
    id: str
    type: str
    plan: str
    amount: int
    status: str
    description: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminWorkspaceDetail(BaseModel):
    """워크스페이스 상세 응답 (멤버·플레이스·빌링 포함)"""
    id: str
    name: str
    slug: str
    plan: str
    is_active: bool
    owner_id: str
    owner_email: str
    owner_name: str
    member_count: int = 0
    place_count: int = 0
    order_count: int = 0
    monthly_spend: int = 0
    members: List[AdminWorkspaceMemberSummary] = []
    places: List[AdminWorkspacePlaceSummary] = []
    recent_billing: List[AdminWorkspaceBillingItem] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminWorkspacePlanPatch(BaseModel):
    """플랜 강제 변경 요청 (어드민 전용)"""
    plan: str = Field(
        description="변경할 플랜 (free / starter / pro / enterprise)",
        pattern="^(free|starter|pro|enterprise)$",
    )
    reason: str = Field(
        min_length=2,
        max_length=500,
        description="변경 사유 (필수)",
    )
    create_billing_record: bool = Field(
        default=True,
        description="BillingHistory 레코드 생성 여부",
    )


class AdminWorkspaceDeactivate(BaseModel):
    """워크스페이스 비활성화 요청"""
    reason: str = Field(
        min_length=2,
        max_length=500,
        description="비활성화 사유",
    )


# ============================================================
# 정산 관리 스키마
# ============================================================

class SettlementItemSchema(BaseModel):
    """정산 상세 항목"""
    id: str
    order_id: str
    amount: int
    commission_amount: int
    # 주문 정보 (조인)
    product_name: Optional[str] = None
    workspace_name: Optional[str] = None
    ordered_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SettlementListItem(BaseModel):
    """정산 목록 아이템"""
    id: str
    media_company_id: str
    media_company_name: str
    month: str                         # YYYY-MM
    status: str                        # pending / approved / paid
    total_orders: int
    total_amount: int
    commission_rate: float
    commission_amount: int
    approved_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SettlementListResponse(BaseModel):
    """정산 목록 페이지네이션 응답"""
    total: int
    items: List[SettlementListItem]


class SettlementDetail(BaseModel):
    """정산 상세 응답 (항목 포함)"""
    id: str
    media_company_id: str
    media_company_name: str
    month: str
    status: str
    total_orders: int
    total_amount: int
    commission_rate: float
    commission_amount: int
    items: List[SettlementItemSchema] = []
    approved_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SettlementGenerateReq(BaseModel):
    """정산 생성 요청"""
    media_company_id: str = Field(description="정산할 미디어사 UUID")
    month: str = Field(
        description="정산 대상 월 (YYYY-MM 형식)",
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
    )
    commission_rate: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="수수료율 (0.0 ~ 1.0, 기본 0.7)",
    )


class SettlementApproveReq(BaseModel):
    """정산 승인 요청 (메모 선택)"""
    note: Optional[str] = Field(
        None,
        max_length=500,
        description="승인 메모",
    )


# ============================================================
# 통계 스키마
# ============================================================

class PlanDistributionStat(BaseModel):
    """플랜별 워크스페이스 분포"""
    free: int = 0
    starter: int = 0
    pro: int = 0
    enterprise: int = 0


class StatsOverview(BaseModel):
    """대시보드 KPI 통계"""
    # 오늘 주문
    today_orders: int = 0
    today_revenue: int = 0
    # 이번 달 신규
    month_new_users: int = 0
    month_new_workspaces: int = 0
    # 구독 매출
    mrr: int = 0                       # Monthly Recurring Revenue
    arr: int = 0                       # Annual Recurring Revenue = MRR × 12
    # 누적 수치
    total_users: int = 0
    total_workspaces: int = 0
    active_workspaces: int = 0
    total_orders: int = 0
    pending_orders: int = 0
    # 플랜 분포
    plan_distribution: PlanDistributionStat = Field(
        default_factory=PlanDistributionStat
    )


class MonthlyRevenueStat(BaseModel):
    """월별 매출 통계 (최근 N개월)"""
    month: str                         # YYYY-MM
    revenue: int                       # 해당 월 총 매출 (paid BillingHistory)
    order_count: int                   # 해당 월 주문 건수
    new_users: int                     # 해당 월 신규 유저 수


class MonthlyRevenueResponse(BaseModel):
    """월별 매출 통계 목록 응답"""
    items: List[MonthlyRevenueStat]
