"""
알림 모델 모듈
Sprint 7: 알림 시스템 구현
Refactor: Base → BaseModel 상속 (UUID PK + timezone-aware 타임스탬프 통일)
- NotificationType: 25가지 알림 타입 enum
- Notification: 알림 데이터 모델
"""

import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class NotificationType(str, enum.Enum):
    """
    알림 타입 열거형 (총 25가지)
    str을 상속하여 JSON 직렬화 및 Pydantic 호환성 확보
    """

    # ── 주문 관련 알림 (8가지) ──────────────────────────────
    ORDER_CREATED = "ORDER_CREATED"           # 주문 생성됨
    ORDER_CONFIRMED = "ORDER_CONFIRMED"       # 주문 확인됨
    ORDER_ASSIGNED = "ORDER_ASSIGNED"         # 매체사 배정됨
    ORDER_IN_PROGRESS = "ORDER_IN_PROGRESS"   # 주문 진행 중
    ORDER_COMPLETED = "ORDER_COMPLETED"       # 주문 완료됨
    ORDER_CANCELLED = "ORDER_CANCELLED"       # 주문 취소됨
    ORDER_REFUND_REQUESTED = "ORDER_REFUND_REQUESTED"  # 환불 요청됨
    ORDER_REFUND_DECIDED = "ORDER_REFUND_DECIDED"      # 환불 결정됨

    # ── 랭킹 관련 알림 (5가지) ──────────────────────────────
    RANK_IMPROVED = "RANK_IMPROVED"           # 순위 상승
    RANK_DROPPED = "RANK_DROPPED"             # 순위 하락
    RANK_TOP10 = "RANK_TOP10"                 # 상위 10위 진입
    RANK_TOP3 = "RANK_TOP3"                   # 상위 3위 진입
    RANK_FLUCTUATION = "RANK_FLUCTUATION"     # 순위 급변동

    # ── 시스템 관련 알림 (5가지) ────────────────────────────
    PLAN_UPGRADED = "PLAN_UPGRADED"           # 플랜 업그레이드
    PLAN_DOWNGRADED = "PLAN_DOWNGRADED"       # 플랜 다운그레이드
    PLAN_EXPIRED = "PLAN_EXPIRED"             # 플랜 만료
    CRAWL_COMPLETED = "CRAWL_COMPLETED"       # 크롤링 완료
    CRAWL_FAILED = "CRAWL_FAILED"             # 크롤링 실패

    # ── 워크스페이스 관련 알림 (4가지) ──────────────────────
    MEMBER_INVITED = "MEMBER_INVITED"         # 멤버 초대됨
    MEMBER_JOINED = "MEMBER_JOINED"           # 멤버 가입함
    MEMBER_LEFT = "MEMBER_LEFT"               # 멤버 탈퇴함
    MEMBER_ROLE_CHANGED = "MEMBER_ROLE_CHANGED"  # 멤버 역할 변경됨

    # ── 결제 관련 알림 (3가지) ──────────────────────────────
    PAYMENT_COMPLETED = "PAYMENT_COMPLETED"   # 결제 완료됨
    PAYMENT_FAILED = "PAYMENT_FAILED"         # 결제 실패됨
    PAYMENT_REFUNDED = "PAYMENT_REFUNDED"     # 결제 환불됨


class Notification(BaseModel):
    """
    알림 모델
    Refactor: Base → BaseModel 상속 (id, created_at, updated_at 자동 관리)

    사용자에게 발송되는 모든 인앱 알림을 저장하는 테이블.
    알림 타입별 data 구조:
      - ORDER_*     : {"order_id": "uuid", "order_number": "ORD-xxx"}
      - RANK_*      : {"place_id": "uuid", "place_name": "str",
                       "keyword": "str", "old_rank": int, "new_rank": int}
      - PLAN_*      : {"old_plan": "str", "new_plan": "str"}
      - CRAWL_*     : {"workspace_id": "uuid", "place_count": int}
      - MEMBER_*    : {"workspace_id": "uuid", "workspace_name": "str",
                       "target_user_name": "str"}
      - PAYMENT_*   : {"order_id": "uuid", "amount": int}
    """

    __tablename__ = "notifications"
    __table_args__ = {"comment": "사용자 인앱 알림"}

    # ── FK: 수신 사용자 ──────────────────────────────────────
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="알림 수신 사용자 ID",
    )

    # ── FK: 워크스페이스 (선택) ──────────────────────────────
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="관련 워크스페이스 ID (없을 수도 있음)",
    )

    # ── 알림 타입 ────────────────────────────────────────────
    type = Column(
        Enum(NotificationType, name="notificationtype"),
        nullable=False,
        index=True,
        comment="알림 타입 (NotificationType enum 값)",
    )

    # ── 알림 제목 ────────────────────────────────────────────
    title = Column(
        String(200),
        nullable=False,
        comment="알림 제목 (최대 200자)",
    )

    # ── 알림 메시지 ──────────────────────────────────────────
    message = Column(
        String(500),
        nullable=False,
        comment="알림 본문 메시지 (최대 500자)",
    )

    # ── 알림 데이터 (타입별 추가 정보) ──────────────────────
    data = Column(
        JSON,
        nullable=False,
        default=dict,
        comment="알림 타입별 추가 데이터 (JSON)",
    )

    # ── 읽음 여부 ────────────────────────────────────────────
    is_read = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="읽음 여부 (기본값: False)",
    )

    # ── 읽은 시각 ────────────────────────────────────────────
    # created_at은 BaseModel에서 자동 관리 (timezone=True, server_default=func.now())
    read_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="알림 읽은 시각 (UTC, 읽지 않으면 None)",
    )

    # ── 관계 ─────────────────────────────────────────────────
    user = relationship("User", back_populates="notifications", lazy="select")
    workspace = relationship("Workspace", back_populates="notifications", lazy="select")

    def __repr__(self) -> str:
        return (
            f"<Notification id={self.id} type={self.type} "
            f"user_id={self.user_id} is_read={self.is_read}>"
        )
