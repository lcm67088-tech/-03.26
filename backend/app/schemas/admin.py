"""
어드민 전용 Pydantic 스키마 (Sprint 6 신규)

AdminOrderListItem    주문 목록 아이템 (어드민 뷰)
AdminOrderDetail      주문 상세 (어드민 뷰, 모든 정보 포함)
OrderStatusUpdate     주문 상태 변경 요청
AssignMediaCompany    미디어사 배정 요청
CompleteOrder         주문 완료 처리 요청
RefundDecision        환불 결정 요청
MediaCompanyCreate    미디어사 등록 요청
MediaCompanyUpdate    미디어사 수정 요청
MediaCompanyResponse  미디어사 응답 (통계 포함)
MediaCompanyDetail    미디어사 상세 (최근 주문 포함)
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================
# 주문 관련 어드민 스키마
# ============================

class AdminOrderListItem(BaseModel):
    """어드민 주문 목록 아이템"""
    id: str
    product_name: str
    status: str
    total_amount: int
    quantity: int
    # 워크스페이스 정보
    workspace_id: str
    workspace_name: str
    workspace_plan: str
    # 장소 정보 (선택)
    place_name: Optional[str] = None
    # 미디어사 정보 (선택)
    media_company_id: Optional[str] = None
    media_company_name: Optional[str] = None
    # 타임스탬프
    ordered_at: Optional[datetime] = None
    updated_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminOrderListResponse(BaseModel):
    """어드민 주문 목록 페이지네이션 응답"""
    total: int
    items: List[AdminOrderListItem]


class AdminPaymentInfo(BaseModel):
    """결제 정보 (어드민 주문 상세용)"""
    id: str
    amount: int
    method: Optional[str] = None
    status: str
    pg_transaction_id: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminOrderDetail(BaseModel):
    """어드민 주문 상세 응답 (모든 정보 포함)"""
    id: str
    product_id: Optional[str] = None
    product_name: str
    description: Optional[str] = None
    status: str
    quantity: int
    unit_price: int
    total_amount: int
    special_requests: Optional[str] = None
    proof_url: Optional[str] = None
    # 워크스페이스 정보
    workspace: Optional[Dict[str, Any]] = None  # { id, name, plan }
    # 장소 정보
    place: Optional[Dict[str, Any]] = None      # { id, name, alias, naver_place_id }
    # 키워드 목록
    keywords: List[Dict[str, Any]] = []          # [{ id, keyword }]
    # 결제 정보
    payment: Optional[AdminPaymentInfo] = None
    # 미디어사 정보
    media_company: Optional[Dict[str, Any]] = None  # { id, name }
    # 어드민 노트 이력 (extra_data.admin_notes)
    admin_notes: List[Dict[str, Any]] = []
    # 타임스탬프
    ordered_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrderStatusUpdate(BaseModel):
    """주문 상태 변경 요청"""
    status: str = Field(
        description="변경할 상태 (confirmed→in_progress, in_progress→completed 등)"
    )
    note: Optional[str] = Field(
        None,
        max_length=500,
        description="처리 메모 (extra_data.admin_notes에 저장)",
    )


class AssignMediaCompany(BaseModel):
    """미디어사 배정 요청"""
    media_company_id: str = Field(description="배정할 미디어사 UUID")


class CompleteOrder(BaseModel):
    """주문 완료 처리 요청"""
    proof_url: str = Field(
        min_length=1,
        max_length=500,
        description="작업 완료 증빙 URL",
    )


class RefundDecision(BaseModel):
    """환불 결정 요청"""
    approve: bool = Field(description="True=환불 승인, False=환불 거부")
    note: str = Field(
        min_length=2,
        max_length=500,
        description="처리 메모 (유저에게 전달될 수 있음)",
    )


# ============================
# 미디어사 관련 스키마
# ============================

class MediaCompanyCreate(BaseModel):
    """미디어사 등록 요청"""
    name: str = Field(
        min_length=1,
        max_length=100,
        description="매체사명 (중복 불가)",
    )
    contact_email: Optional[str] = Field(
        None,
        max_length=255,
        description="담당자 이메일",
    )
    contact_phone: Optional[str] = Field(
        None,
        max_length=20,
        description="담당자 전화번호",
    )
    bank_account: Optional[str] = Field(
        None,
        max_length=200,
        description="정산 계좌 (예: 신한은행 110-123-456789 홍길동)",
    )


class MediaCompanyUpdate(BaseModel):
    """미디어사 수정 요청 (모든 필드 선택적)"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    contact_email: Optional[str] = Field(None, max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=20)
    bank_account: Optional[str] = Field(None, max_length=200)
    is_active: Optional[bool] = None


class MediaCompanyResponse(BaseModel):
    """미디어사 목록 아이템 (통계 포함)"""
    id: str
    name: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    bank_account: Optional[str] = None
    is_active: bool
    # 통계 필드 (DB에서 별도 계산)
    order_count: int = 0
    completed_count: int = 0
    avg_completion_days: Optional[float] = None

    model_config = {"from_attributes": True}


class RecentOrderForMedia(BaseModel):
    """미디어사 상세에서 최근 주문 요약"""
    id: str
    product_name: str
    status: str
    total_amount: int
    workspace_name: str
    ordered_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class MediaCompanyDetail(BaseModel):
    """미디어사 상세 (최근 주문 10개 포함)"""
    id: str
    name: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    bank_account: Optional[str] = None
    is_active: bool
    order_count: int = 0
    completed_count: int = 0
    avg_completion_days: Optional[float] = None
    recent_orders: List[RecentOrderForMedia] = []

    model_config = {"from_attributes": True}
