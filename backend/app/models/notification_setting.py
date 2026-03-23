"""
알림 설정 모델 모듈
Sprint 7: 알림 시스템 구현
Refactor: Base → BaseModel 상속 (UUID PK + timezone-aware 타임스탬프 통일)
- NotificationSetting: 사용자별 알림 타입 수신 채널 설정 모델
"""

from sqlalchemy import Boolean, Column, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel
from app.models.notification import NotificationType


class NotificationSetting(BaseModel):
    """
    알림 설정 모델
    Refactor: Base → BaseModel 상속 (id, created_at, updated_at 자동 관리)

    사용자가 각 알림 타입별로 어떤 채널(인앱/이메일/카카오/SMS)로
    수신할지 선택한 설정값을 저장합니다.

    UniqueConstraint(user_id, notification_type) 적용으로
    사용자당 알림 타입별 1행 보장.
    """

    __tablename__ = "notification_settings"

    # ── 복합 유니크 제약 ─────────────────────────────────────
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "notification_type",
            name="uq_notification_settings_user_type",
        ),
        {"comment": "사용자 알림 수신 채널 설정"},
    )

    # ── FK: 설정 소유자 ──────────────────────────────────────
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="설정 소유 사용자 ID",
    )

    # ── 알림 타입 ────────────────────────────────────────────
    notification_type = Column(
        Enum(NotificationType, name="notificationtype", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        comment="설정 대상 알림 타입",
    )

    # ── 채널별 수신 여부 ─────────────────────────────────────
    in_app_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="인앱 알림 수신 여부 (기본값: True)",
    )

    email_enabled = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="이메일 알림 수신 여부 (기본값: False)",
    )

    kakao_enabled = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="카카오 알림 수신 여부 (기본값: False, Mock 처리)",
    )

    sms_enabled = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="SMS 알림 수신 여부 (기본값: False, Mock 처리)",
    )

    # created_at, updated_at → BaseModel에서 자동 관리
    # (timezone=True, server_default=func.now(), onupdate=func.now())

    # ── 관계 ─────────────────────────────────────────────────
    user = relationship(
        "User",
        back_populates="notification_settings",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationSetting user_id={self.user_id} "
            f"type={self.notification_type} "
            f"in_app={self.in_app_enabled} email={self.email_enabled}>"
        )
