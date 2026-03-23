"""
Alembic 마이그레이션: 004_add_notifications
Sprint 7: notifications 테이블 및 notification_settings 테이블 생성

Revision ID: 004
Revises: 003_add_orders
Create Date: 2026-03-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# ── 마이그레이션 메타데이터 ─────────────────────────────────
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

# ── NotificationType enum 값 목록 ────────────────────────────
NOTIFICATION_TYPE_VALUES = [
    # 주문 관련 (8가지)
    "ORDER_CREATED",
    "ORDER_CONFIRMED",
    "ORDER_ASSIGNED",
    "ORDER_IN_PROGRESS",
    "ORDER_COMPLETED",
    "ORDER_CANCELLED",
    "ORDER_REFUND_REQUESTED",
    "ORDER_REFUND_DECIDED",
    # 랭킹 관련 (5가지)
    "RANK_IMPROVED",
    "RANK_DROPPED",
    "RANK_TOP10",
    "RANK_TOP3",
    "RANK_FLUCTUATION",
    # 시스템 관련 (5가지)
    "PLAN_UPGRADED",
    "PLAN_DOWNGRADED",
    "PLAN_EXPIRED",
    "CRAWL_COMPLETED",
    "CRAWL_FAILED",
    # 워크스페이스 관련 (4가지)
    "MEMBER_INVITED",
    "MEMBER_JOINED",
    "MEMBER_LEFT",
    "MEMBER_ROLE_CHANGED",
    # 결제 관련 (3가지)
    "PAYMENT_COMPLETED",
    "PAYMENT_FAILED",
    "PAYMENT_REFUNDED",
]


def upgrade() -> None:
    """
    notifications 테이블과 notification_settings 테이블을 생성합니다.

    1. notificationtype enum 타입 생성 (PostgreSQL)
    2. notifications 테이블 생성
    3. notification_settings 테이블 생성
    4. 인덱스 및 제약 조건 추가
    """

    # ── 1. notificationtype enum 타입 생성 ────────────────────
    # PostgreSQL의 경우 Enum 타입을 별도로 생성해야 함
    notification_type_enum = postgresql.ENUM(
        *NOTIFICATION_TYPE_VALUES,
        name="notificationtype",
        create_type=True,
    )
    notification_type_enum.create(op.get_bind(), checkfirst=True)

    # ── 2. notifications 테이블 생성 ──────────────────────────
    op.create_table(
        "notifications",
        # 기본키
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="알림 고유 식별자",
        ),
        # 수신 사용자 FK
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="알림 수신 사용자 ID",
        ),
        # 워크스페이스 FK (nullable)
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=True,
            comment="관련 워크스페이스 ID",
        ),
        # 알림 타입 (enum)
        sa.Column(
            "type",
            postgresql.ENUM(*NOTIFICATION_TYPE_VALUES, name="notificationtype", create_type=False),
            nullable=False,
            comment="알림 타입",
        ),
        # 제목
        sa.Column(
            "title",
            sa.String(200),
            nullable=False,
            comment="알림 제목",
        ),
        # 본문 메시지
        sa.Column(
            "message",
            sa.String(500),
            nullable=False,
            comment="알림 본문 메시지",
        ),
        # 추가 데이터 (JSON)
        sa.Column(
            "data",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
            comment="알림 타입별 추가 데이터",
        ),
        # 읽음 여부
        sa.Column(
            "is_read",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="읽음 여부",
        ),
        # 생성 시각
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            comment="알림 생성 시각 (UTC)",
        ),
        # 읽은 시각
        sa.Column(
            "read_at",
            sa.DateTime(),
            nullable=True,
            comment="알림 읽은 시각 (UTC)",
        ),
    )

    # notifications 인덱스
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_workspace_id", "notifications", ["workspace_id"])
    op.create_index("ix_notifications_type", "notifications", ["type"])
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
    # 사용자별 읽지 않은 알림 조회를 위한 복합 인덱스
    op.create_index(
        "ix_notifications_user_unread",
        "notifications",
        ["user_id", "is_read"],
    )

    # ── 3. notification_settings 테이블 생성 ──────────────────
    op.create_table(
        "notification_settings",
        # 기본키
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="알림 설정 고유 식별자",
        ),
        # 사용자 FK
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="설정 소유 사용자 ID",
        ),
        # 알림 타입 (enum)
        sa.Column(
            "notification_type",
            postgresql.ENUM(*NOTIFICATION_TYPE_VALUES, name="notificationtype", create_type=False),
            nullable=False,
            comment="설정 대상 알림 타입",
        ),
        # 인앱 알림 수신 여부
        sa.Column(
            "in_app_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="인앱 알림 수신 여부",
        ),
        # 이메일 알림 수신 여부
        sa.Column(
            "email_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="이메일 알림 수신 여부",
        ),
        # 카카오 알림 수신 여부
        sa.Column(
            "kakao_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="카카오 알림 수신 여부",
        ),
        # SMS 알림 수신 여부
        sa.Column(
            "sms_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="SMS 알림 수신 여부",
        ),
        # 생성 시각
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            comment="설정 생성 시각 (UTC)",
        ),
        # 수정 시각
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            comment="설정 마지막 수정 시각 (UTC)",
        ),
        # 복합 유니크 제약: 사용자당 알림 타입별 1행
        sa.UniqueConstraint(
            "user_id",
            "notification_type",
            name="uq_notification_settings_user_type",
        ),
    )

    # notification_settings 인덱스
    op.create_index(
        "ix_notification_settings_user_id",
        "notification_settings",
        ["user_id"],
    )


def downgrade() -> None:
    """
    Sprint 7에서 추가된 테이블과 enum 타입을 삭제합니다.
    """
    # notification_settings 테이블 삭제
    op.drop_index("ix_notification_settings_user_id", table_name="notification_settings")
    op.drop_table("notification_settings")

    # notifications 테이블 삭제
    op.drop_index("ix_notifications_user_unread", table_name="notifications")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_is_read", table_name="notifications")
    op.drop_index("ix_notifications_type", table_name="notifications")
    op.drop_index("ix_notifications_workspace_id", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")

    # notificationtype enum 타입 삭제
    notification_type_enum = postgresql.ENUM(
        name="notificationtype",
        create_type=False,
    )
    notification_type_enum.drop(op.get_bind(), checkfirst=True)
