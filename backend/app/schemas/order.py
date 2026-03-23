"""
주문(Order) 관련 Pydantic 스키마 (Sprint 5 완성 + Sprint 12 카테고리/일정 추가)

ProductTypeWithProducts  상품 목록 응답 (유형별 그룹)
ProductResponse          단일 상품 응답
OrderCreateRequest       주문 생성 요청
OrderListItem            목록 응답 아이템
OrderListResponse        페이지네이션 래퍼
OrderDetail              주문 상세 응답
PaymentCompleteRequest   Mock 결제 완료 요청
RefundRequestBody        환불 요청 Body
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================
# 상품 스키마
# ============================

class ProductResponse(BaseModel):
    """단일 상품 응답"""
    id: str
    name: str
    description: Optional[str] = None
    base_price: int
    unit: str
    min_quantity: int
    max_quantity: Optional[int] = None
    badge: Optional[str] = None       # extra_data.badge
    features: List[str] = []          # extra_data.features

    model_config = {"from_attributes": True}


class ProductTypeWithProducts(BaseModel):
    """상품 유형 + 소속 상품 목록"""
    id: str
    name: str
    description: Optional[str] = None
    products: List[ProductResponse] = []

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    """상품 목록 응답 (유형별 그룹)"""
    product_types: List[ProductTypeWithProducts]


# ============================
# 주문 요청 스키마
# ============================

class OrderCreateRequest(BaseModel):
    """주문 생성 요청"""
    workspace_id: str
    product_id: str
    place_id: Optional[str] = None
    keyword_ids: Optional[List[str]] = []
    quantity: int = Field(ge=1, description="주문 수량 (최소 1)")
    daily_qty: Optional[int] = Field(None, ge=1, description="일 수량 (트래픽·저장 등)")
    start_date: Optional[date] = Field(None, description="작업 시작일 (YYYY-MM-DD)")
    end_date: Optional[date] = Field(None, description="작업 종료일 (YYYY-MM-DD)")
    category: Optional[str] = Field(
        None,
        description="주문 카테고리 (blog/reward_traffic/reward_save/receipt/sns)",
    )
    payment_method: str = Field(
        description="결제 수단 (kakaopay | naverpay | card)"
    )
    special_requests: Optional[str] = Field(
        None,
        max_length=1000,
        description="특이사항",
    )


class PaymentCompleteRequest(BaseModel):
    """Mock PG 결제 완료 요청"""
    pg_transaction_id: str = Field(description="PG사 트랜잭션 ID")
    method: str = Field(description="결제 수단 (kakaopay | naverpay | card)")


class RefundRequestBody(BaseModel):
    """환불 요청 Body"""
    reason: str = Field(
        min_length=10,
        max_length=500,
        description="환불 사유 (최소 10자)",
    )


# ============================
# 주문 응답 스키마
# ============================

class OrderListItem(BaseModel):
    """주문 목록 아이템"""
    id: str
    product_name: str
    category: Optional[str] = None
    status: str
    total_amount: int
    quantity: int
    unit_price: int
    daily_qty: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    place_name: Optional[str] = None
    place_naver_id: Optional[str] = None  # 네이버 MID
    ordered_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderListResponse(BaseModel):
    """주문 목록 페이지네이션 응답"""
    total: int
    items: List[OrderListItem]


class PaymentInfo(BaseModel):
    """결제 정보 (OrderDetail 내부)"""
    id: str
    amount: int
    method: Optional[str] = None
    status: str
    pg_transaction_id: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderDetail(BaseModel):
    """주문 상세 응답"""
    id: str
    product_id: Optional[str] = None
    product_name: str
    category: Optional[str] = None
    description: Optional[str] = None
    status: str
    quantity: int
    unit_price: int
    total_amount: int
    daily_qty: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    special_requests: Optional[str] = None
    # 장소 정보
    place: Optional[Dict[str, Any]] = None    # { id, name, alias, naver_place_id }
    # 선택된 키워드
    keywords: List[Dict[str, Any]] = []       # [{ id, keyword }]
    # 결제 정보
    payment: Optional[PaymentInfo] = None
    # 매체사 배정 (어드민용)
    media_company_id: Optional[str] = None
    media_company_name: Optional[str] = None
    # 증빙
    proof_url: Optional[str] = None
    # 타임스탬프
    ordered_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateOrderResponse(BaseModel):
    """주문 생성 응답 (order + payment 함께 반환)"""
    order: OrderDetail
    payment: PaymentInfo
