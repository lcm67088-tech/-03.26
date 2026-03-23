"""
빌링 Pydantic 스키마
Sprint 8: 구독/결제 내역 요청·응답 스키마 정의

- SubscriptionResponse     : 구독 정보 응답
- BillingHistoryResponse   : 단건 결제 내역 응답
- BillingHistoryListResponse: 결제 내역 목록 응답 (페이지네이션)
- PlanUpgradeRequest       : 플랜 업그레이드/다운그레이드 요청
- PlanUpgradeResponse      : 플랜 변경 결과 응답
- CancelSubscriptionRequest: 구독 취소 요청
- PaymentMethodRequest     : 결제 수단 등록/변경 요청
- PaymentMethodResponse    : 결제 수단 조회 응답
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, field_validator, ConfigDict


# ─────────────────────────────────────────────────────────────
# 구독 응답 스키마
# ─────────────────────────────────────────────────────────────

class SubscriptionResponse(BaseModel):
    """현재 구독 정보 응답"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    plan: str
    billing_cycle: str                     # monthly / yearly
    status: str                            # active / cancelled / past_due / expired
    amount: int                            # 월 결제 금액 (원)
    started_at: datetime
    next_billing_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class SubscriptionWithLimitsResponse(SubscriptionResponse):
    """
    플랜 한도 포함 구독 응답
    GET /billing/subscription 에서 사용
    """
    plan_limits: Dict[str, Any]            # {"max_places": 5, "max_keywords": 30, ...}
    plan_price_monthly: int                # 월간 결제 시 금액
    plan_price_yearly: int                 # 연간 결제 시 월 환산 금액
    # 현재 사용량 (별도 쿼리로 채워서 반환)
    current_places: int = 0
    current_keywords: int = 0


# ─────────────────────────────────────────────────────────────
# 결제 내역 스키마
# ─────────────────────────────────────────────────────────────

class BillingHistoryResponse(BaseModel):
    """단건 결제 내역 응답"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    subscription_id: Optional[UUID] = None
    type: str                              # subscription / upgrade / downgrade / refund
    plan: str
    billing_cycle: str
    amount: int
    status: str                            # paid / failed / refunded
    pg_transaction_id: Optional[str] = None
    description: str
    created_at: datetime


class BillingHistoryListResponse(BaseModel):
    """결제 내역 목록 응답 (페이지네이션)"""

    items: List[BillingHistoryResponse]
    total: int
    page: int
    limit: int


# ─────────────────────────────────────────────────────────────
# 플랜 변경 요청/응답 스키마
# ─────────────────────────────────────────────────────────────

class PlanUpgradeRequest(BaseModel):
    """플랜 업그레이드 / 다운그레이드 요청"""

    plan: str               # starter / pro / enterprise (또는 free)
    billing_cycle: str      # monthly / yearly

    @field_validator("plan")
    @classmethod
    def validate_plan(cls, v: str) -> str:
        valid_plans = ["free", "starter", "pro", "enterprise"]
        if v not in valid_plans:
            raise ValueError(f"올바르지 않은 플랜입니다. 허용값: {valid_plans}")
        return v

    @field_validator("billing_cycle")
    @classmethod
    def validate_billing_cycle(cls, v: str) -> str:
        if v not in ["monthly", "yearly"]:
            raise ValueError("결제 주기는 monthly 또는 yearly여야 합니다.")
        return v


class PlanUpgradeResponse(BaseModel):
    """플랜 변경 결과 응답"""

    subscription: SubscriptionResponse
    billing_history: BillingHistoryResponse
    message: str
    # 다운그레이드 시 비활성화된 수량 (업그레이드 시 0)
    deactivated_places: int = 0
    deactivated_keywords: int = 0


# ─────────────────────────────────────────────────────────────
# 구독 취소 요청
# ─────────────────────────────────────────────────────────────

class CancelSubscriptionRequest(BaseModel):
    """구독 취소 요청"""

    reason: Optional[str] = None       # 취소 사유 (선택)


# ─────────────────────────────────────────────────────────────
# 결제 수단 스키마
# ─────────────────────────────────────────────────────────────

class PaymentMethodRequest(BaseModel):
    """결제 수단 등록/변경 요청"""

    card_number_last4: str             # 카드번호 끝 4자리
    card_brand: str                    # Visa / Mastercard / 국내카드
    exp_month: str                     # 유효기간 월 (MM)
    exp_year: str                      # 유효기간 연 (YY)
    pg_customer_id: Optional[str] = None  # PG 고객 ID (Mock)

    @field_validator("card_number_last4")
    @classmethod
    def validate_last4(cls, v: str) -> str:
        if not v.isdigit() or len(v) != 4:
            raise ValueError("카드번호 끝 4자리는 숫자 4자리여야 합니다.")
        return v

    @field_validator("exp_month")
    @classmethod
    def validate_exp_month(cls, v: str) -> str:
        if not v.isdigit() or not (1 <= int(v) <= 12):
            raise ValueError("유효기간 월은 01~12 사이여야 합니다.")
        return v.zfill(2)

    @field_validator("exp_year")
    @classmethod
    def validate_exp_year(cls, v: str) -> str:
        if not v.isdigit() or len(v) not in [2, 4]:
            raise ValueError("유효기간 연도는 YY 또는 YYYY 형식이어야 합니다.")
        # 2자리면 YY 그대로 저장
        return v[-2:]


class PaymentMethodResponse(BaseModel):
    """결제 수단 응답"""

    card_number_last4: str
    card_brand: str
    exp_month: str
    exp_year: str
    pg_customer_id: Optional[str] = None
    # 표시용 마스킹 문자열 (예: "Visa **** 1234 (12/27)")
    display: str = ""

    def model_post_init(self, __context: Any) -> None:
        """display 필드 자동 생성"""
        if not self.display:
            self.display = (
                f"{self.card_brand} **** {self.card_number_last4} "
                f"({self.exp_month}/{self.exp_year})"
            )
