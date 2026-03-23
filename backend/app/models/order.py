"""
Order 및 Payment 모델 (Sprint 5 보완 + Sprint 12 카테고리/일정 추가)

주문 생성부터 완료까지의 전체 상태 관리.
Sprint 5에서 추가된 컬럼:
  - product_id: 상품 FK
  - keyword_ids: 선택된 키워드 UUID 목록 (JSONB)
  - quantity: 주문 수량
  - unit_price: 단가 (원)
  - special_requests: 특이사항
Sprint 12에서 추가된 컬럼:
  - category: 주문 카테고리 (blog/reward_traffic/reward_save/receipt/sns)
  - daily_qty: 일 수량 (트래픽·저장 등 일별 작업 단위)
  - start_date: 작업 시작일
  - end_date: 작업 종료일
"""
import enum

from sqlalchemy import Column, Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class OrderCategory(str, enum.Enum):
    """
    주문 카테고리 — 프론트 통일 기준
    blog          : 블로그 리뷰
    reward_traffic: 리워드 유입 (트래픽)
    reward_save   : 리워드 저장하기
    receipt       : 영수증 리뷰
    sns           : SNS (인스타그램 등)
    """
    BLOG           = "blog"
    REWARD_TRAFFIC = "reward_traffic"
    REWARD_SAVE    = "reward_save"
    RECEIPT        = "receipt"
    SNS            = "sns"


class OrderStatus(str, enum.Enum):
    """
    주문 상태 머신
    pending → confirmed → in_progress → completed
                       ↘ cancelled
                                    ↘ refunded
                                    ↘ disputed
    """
    PENDING = "pending"          # 결제 완료, 어드민 확인 대기
    CONFIRMED = "confirmed"      # 어드민 확인, 매체사 배정 완료
    IN_PROGRESS = "in_progress"  # 작업 진행 중
    COMPLETED = "completed"      # 작업 완료
    CANCELLED = "cancelled"      # 취소됨
    REFUNDED = "refunded"        # 환불 완료
    DISPUTED = "disputed"        # 분쟁 처리 중


class PaymentMethod(str, enum.Enum):
    """결제 수단"""
    KAKAOPAY = "kakaopay"
    NAVERPAY = "naverpay"
    CARD = "card"


class PaymentStatus(str, enum.Enum):
    """결제 상태"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class Order(BaseModel):
    """
    주문 테이블
    유저가 생성한 마케팅 서비스 주문
    
    Relations:
        - workspace: 주문한 워크스페이스
        - place: 대상 플레이스
        - media_company: 배정된 매체사
        - payment: 결제 정보
    """
    __tablename__ = "orders"
    __table_args__ = {"comment": "주문 정보"}

    # 주문 주체
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="워크스페이스 FK",
    )

    # 상품 FK (Sprint 5 추가)
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="주문 상품 FK",
    )

    # 대상 플레이스 (선택적)
    place_id = Column(
        UUID(as_uuid=True),
        ForeignKey("places.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="대상 플레이스 FK (없으면 NULL)",
    )

    # 선택된 키워드 ID 목록 (Sprint 5 추가)
    keyword_ids = Column(
        JSONB,
        nullable=True,
        default=list,
        comment="선택된 키워드 UUID 목록 (JSONB 배열)",
    )

    # 주문 카테고리 (Sprint 12 추가)
    category = Column(
        Enum(OrderCategory),
        nullable=True,
        index=True,
        comment="주문 카테고리 (blog/reward_traffic/reward_save/receipt/sns)",
    )

    # 일 수량 (Sprint 12 추가) — 트래픽·저장하기 등 일별 작업 수
    daily_qty = Column(
        Integer,
        nullable=True,
        comment="일 수량 (예: 저장하기 200/일)",
    )

    # 작업 기간 (Sprint 12 추가)
    start_date = Column(
        Date,
        nullable=True,
        comment="작업 시작일",
    )
    end_date = Column(
        Date,
        nullable=True,
        comment="작업 종료일",
    )

    # 주문 정보
    product_name = Column(
        String(200),
        nullable=False,
        comment="주문 상품명 (스냅샷)",
    )
    description = Column(
        String(1000),
        nullable=True,
        comment="주문 설명",
    )

    # 수량 및 금액 (Sprint 5 추가)
    quantity = Column(
        Integer,
        nullable=False,
        default=1,
        comment="주문 수량",
    )
    unit_price = Column(
        Integer,
        nullable=False,
        default=0,
        comment="단가 (원 단위)",
    )
    total_amount = Column(
        Integer,
        nullable=False,
        comment="주문 금액 (원 단위) = quantity × unit_price",
    )

    # 특이사항 (Sprint 5 추가)
    special_requests = Column(
        Text,
        nullable=True,
        comment="특이사항 / 요청사항",
    )

    # 상태
    status = Column(
        Enum(OrderStatus),
        default=OrderStatus.PENDING,
        nullable=False,
        index=True,
        comment="주문 상태",
    )

    # 매체사 배정 (어드민이 배정)
    media_company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("media_companies.id", ondelete="SET NULL"),
        nullable=True,
        comment="배정된 매체사 FK",
    )

    # 작업 완료 증빙
    proof_url = Column(
        String(500),
        nullable=True,
        comment="작업 완료 증빙 URL",
    )

    # 타임스탬프
    ordered_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="주문 시간 (결제 완료 시점)",
    )
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="작업 완료 시간",
    )

    # 추가 데이터
    extra_data = Column(
        JSONB,
        nullable=True,
        default=dict,
        comment="추가 정보",
    )

    # Relations
    workspace = relationship("Workspace", back_populates="orders")
    place = relationship("Place", back_populates="orders")
    product = relationship("Product")
    media_company = relationship("MediaCompany", back_populates="orders")
    payment = relationship(
        "Payment",
        back_populates="order",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Order {self.product_name} [{self.status}]>"


class Payment(BaseModel):
    """
    결제 테이블
    주문과 1:1 관계, PG 결제 정보 저장
    
    Relations:
        - order: 연결된 주문
    """
    __tablename__ = "payments"
    __table_args__ = {"comment": "결제 정보"}

    # 연결된 주문 (1:1)
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        comment="주문 FK (1:1)",
    )

    # 결제 정보
    amount = Column(
        Integer,
        nullable=False,
        comment="결제 금액 (원 단위)",
    )
    method = Column(
        Enum(PaymentMethod),
        nullable=False,
        comment="결제 수단",
    )
    status = Column(
        Enum(PaymentStatus),
        default=PaymentStatus.PENDING,
        nullable=False,
        comment="결제 상태",
    )

    # PG 트랜잭션 ID
    pg_transaction_id = Column(
        String(200),
        nullable=True,
        comment="PG사 트랜잭션 ID",
    )

    # 타임스탬프
    paid_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="결제 완료 시간",
    )

    # Relations
    order = relationship("Order", back_populates="payment")

    def __repr__(self) -> str:
        return f"<Payment {self.amount}원 [{self.status}]>"
