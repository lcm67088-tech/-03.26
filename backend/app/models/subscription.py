"""
구독 및 결제 내역 모델
Sprint 8: 빌링 + 플랜 관리 시스템 구현

- Subscription  : 워크스페이스의 현재 구독 정보
- BillingHistory: 결제/변경 이력 (업그레이드, 다운그레이드, 환불 등)
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class Subscription(Base):
    """
    구독 테이블

    워크스페이스의 현재 플랜 구독 상태를 관리합니다.
    한 워크스페이스에 활성(active) 구독은 최대 1개입니다.

    status 값:
      - active    : 정상 구독 중
      - cancelled : 취소됨 (next_billing_at까지 유지)
      - past_due  : 결제 실패로 연체 상태
      - expired   : 만료됨
    """

    __tablename__ = "subscriptions"
    __table_args__ = {"comment": "워크스페이스 구독 정보"}

    # ── PK ──────────────────────────────────────────────────
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        comment="구독 고유 식별자 (UUID v4)",
    )

    # ── FK: 워크스페이스 ─────────────────────────────────────
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="워크스페이스 FK",
    )

    # ── 플랜 정보 ────────────────────────────────────────────
    plan = Column(
        String(20),
        nullable=False,
        comment="플랜 (free/starter/pro/enterprise)",
    )

    # ── 결제 주기 ────────────────────────────────────────────
    billing_cycle = Column(
        String(10),
        nullable=False,
        default="monthly",
        comment="결제 주기 (monthly/yearly)",
    )

    # ── 구독 상태 ────────────────────────────────────────────
    status = Column(
        String(20),
        nullable=False,
        default="active",
        index=True,
        comment="구독 상태 (active/cancelled/past_due/expired)",
    )

    # ── 결제 금액 (원 단위) ──────────────────────────────────
    amount = Column(
        Integer,
        nullable=False,
        default=0,
        comment="월 결제 금액 (원 단위)",
    )

    # ── 구독 시작일 ──────────────────────────────────────────
    started_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="구독 시작 시각 (UTC)",
    )

    # ── 다음 결제일 ──────────────────────────────────────────
    next_billing_at = Column(
        DateTime,
        nullable=True,
        comment="다음 결제 예정 시각 (UTC, free 플랜은 null)",
    )

    # ── 구독 취소일 ──────────────────────────────────────────
    cancelled_at = Column(
        DateTime,
        nullable=True,
        comment="구독 취소 시각 (UTC)",
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
    workspace = relationship("Workspace", back_populates="subscriptions")
    billing_histories = relationship(
        "BillingHistory",
        back_populates="subscription",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Subscription workspace={self.workspace_id} "
            f"plan={self.plan} status={self.status}>"
        )


class BillingHistory(Base):
    """
    결제 내역 테이블

    구독 생성, 업그레이드, 다운그레이드, 환불 등
    모든 결제 관련 이벤트를 불변(immutable) 로그로 저장합니다.

    type 값:
      - subscription : 신규 구독
      - upgrade      : 플랜 업그레이드
      - downgrade    : 플랜 다운그레이드
      - refund       : 환불

    status 값:
      - paid    : 결제 완료
      - failed  : 결제 실패
      - refunded: 환불 처리됨
    """

    __tablename__ = "billing_histories"
    __table_args__ = {"comment": "결제 내역 이력"}

    # ── PK ──────────────────────────────────────────────────
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        comment="결제 내역 고유 식별자 (UUID v4)",
    )

    # ── FK: 워크스페이스 ─────────────────────────────────────
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="워크스페이스 FK",
    )

    # ── FK: 구독 (nullable) ───────────────────────────────────
    subscription_id = Column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="관련 구독 FK (구독 삭제 시 null 유지)",
    )

    # ── 내역 타입 ────────────────────────────────────────────
    type = Column(
        String(20),
        nullable=False,
        index=True,
        comment="내역 타입 (subscription/upgrade/downgrade/refund)",
    )

    # ── 플랜 정보 ────────────────────────────────────────────
    plan = Column(
        String(20),
        nullable=False,
        comment="적용된 플랜명",
    )

    # ── 결제 주기 ────────────────────────────────────────────
    billing_cycle = Column(
        String(10),
        nullable=False,
        default="monthly",
        comment="결제 주기 (monthly/yearly)",
    )

    # ── 금액 (원 단위) ───────────────────────────────────────
    amount = Column(
        Integer,
        nullable=False,
        default=0,
        comment="결제 금액 (원 단위, 환불/무료는 0)",
    )

    # ── 결제 상태 ────────────────────────────────────────────
    status = Column(
        String(20),
        nullable=False,
        default="paid",
        index=True,
        comment="결제 상태 (paid/failed/refunded)",
    )

    # ── PG 트랜잭션 ID ───────────────────────────────────────
    pg_transaction_id = Column(
        String(100),
        nullable=True,
        comment="PG 트랜잭션 ID (Mock: mock_upgrade_{timestamp})",
    )

    # ── 설명 ─────────────────────────────────────────────────
    description = Column(
        String(200),
        nullable=False,
        default="",
        comment="내역 설명 (예: 'Pro 플랜으로 업그레이드')",
    )

    # ── 생성 시각 ────────────────────────────────────────────
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="결제 처리 시각 (UTC)",
    )

    # ── 관계 ─────────────────────────────────────────────────
    workspace = relationship("Workspace", back_populates="billing_histories")
    subscription = relationship("Subscription", back_populates="billing_histories")

    def __repr__(self) -> str:
        return (
            f"<BillingHistory workspace={self.workspace_id} "
            f"type={self.type} plan={self.plan} amount={self.amount} status={self.status}>"
        )
