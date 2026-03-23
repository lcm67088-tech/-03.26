"""
정산(Settlement) 모델
Sprint 9: 어드민 심화 — 미디어사 월별 정산 관리

- Settlement     : 미디어사별 월별 정산 헤더
- SettlementItem : 정산에 포함된 개별 주문 라인
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class Settlement(Base):
    """
    정산 테이블 (헤더)

    미디어사별 월별 정산을 관리합니다.
    한 미디어사에 동일 월 정산은 최대 1개입니다.

    status 값:
      - pending  : 정산 생성됨, 승인 대기
      - approved : 어드민 승인 완료
      - paid     : 실제 지급 완료
    """

    __tablename__ = "settlements"
    __table_args__ = {"comment": "미디어사 월별 정산 헤더"}

    # ── PK ──────────────────────────────────────────────────
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        comment="정산 고유 식별자 (UUID v4)",
    )

    # ── FK: 미디어사 ─────────────────────────────────────────
    media_company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("media_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="미디어사 FK",
    )

    # ── 정산 월 ──────────────────────────────────────────────
    month = Column(
        String(7),
        nullable=False,
        index=True,
        comment="정산 대상 월 (예: 2026-03)",
    )

    # ── 정산 상태 ────────────────────────────────────────────
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="정산 상태 (pending/approved/paid)",
    )

    # ── 집계 정보 ────────────────────────────────────────────
    total_orders = Column(
        Integer,
        nullable=False,
        default=0,
        comment="총 주문 건수",
    )
    total_amount = Column(
        Integer,
        nullable=False,
        default=0,
        comment="총 주문 금액 (원 단위)",
    )

    # ── 수수료 정보 ──────────────────────────────────────────
    commission_rate = Column(
        Float,
        nullable=False,
        default=0.7,
        comment="미디어사 수취 비율 (예: 0.7 = 70%)",
    )
    commission_amount = Column(
        Integer,
        nullable=False,
        default=0,
        comment="실제 지급액 = round(total_amount * commission_rate)",
    )

    # ── 처리 일시 ────────────────────────────────────────────
    approved_at = Column(
        DateTime,
        nullable=True,
        comment="승인 시각 (UTC)",
    )
    paid_at = Column(
        DateTime,
        nullable=True,
        comment="지급 완료 시각 (UTC)",
    )

    # ── 생성/수정 시각 ───────────────────────────────────────
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="생성 시각 (UTC)",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="수정 시각 (UTC)",
    )

    # ── 관계 ─────────────────────────────────────────────────
    media_company = relationship("MediaCompany", back_populates="settlements")
    items = relationship(
        "SettlementItem",
        back_populates="settlement",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Settlement media={self.media_company_id} "
            f"month={self.month} status={self.status} amount={self.total_amount}>"
        )


class SettlementItem(Base):
    """
    정산 상세 항목 테이블

    정산에 포함된 개별 주문(Order)을 기록합니다.
    한 주문은 한 정산 아이템에만 포함됩니다.
    """

    __tablename__ = "settlement_items"
    __table_args__ = {"comment": "정산 상세 항목 (주문별)"}

    # ── PK ──────────────────────────────────────────────────
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        comment="정산 항목 고유 식별자 (UUID v4)",
    )

    # ── FK: 정산 헤더 ────────────────────────────────────────
    settlement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("settlements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="정산 헤더 FK",
    )

    # ── FK: 주문 ─────────────────────────────────────────────
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="주문 FK",
    )

    # ── 금액 ─────────────────────────────────────────────────
    amount = Column(
        Integer,
        nullable=False,
        default=0,
        comment="해당 주문 금액 (원 단위)",
    )
    commission_amount = Column(
        Integer,
        nullable=False,
        default=0,
        comment="해당 주문 지급액 = round(amount * commission_rate)",
    )

    # ── 생성 시각 ────────────────────────────────────────────
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="생성 시각 (UTC)",
    )

    # ── 관계 ─────────────────────────────────────────────────
    settlement = relationship("Settlement", back_populates="items")
    order = relationship("Order")

    def __repr__(self) -> str:
        return (
            f"<SettlementItem settlement={self.settlement_id} "
            f"order={self.order_id} amount={self.amount}>"
        )
