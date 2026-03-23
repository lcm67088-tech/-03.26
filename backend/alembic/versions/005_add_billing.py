"""
Alembic 마이그레이션: 005_add_billing
Sprint 8: subscriptions / billing_histories 테이블 생성
         workspaces 테이블에 payment_method JSON 컬럼 추가

Revision ID: 005
Revises: 004
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# ── 마이그레이션 메타데이터 ─────────────────────────────────
revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    1. subscriptions 테이블 생성
    2. billing_histories 테이블 생성
    3. workspaces 테이블에 payment_method JSON 컬럼 추가
    """

    # ── 1. subscriptions 테이블 생성 ──────────────────────────
    op.create_table(
        "subscriptions",
        # PK
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="구독 고유 식별자 (UUID v4)",
        ),
        # 워크스페이스 FK
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            comment="워크스페이스 FK",
        ),
        # 플랜명
        sa.Column(
            "plan",
            sa.String(20),
            nullable=False,
            comment="플랜 (free/starter/pro/enterprise)",
        ),
        # 결제 주기
        sa.Column(
            "billing_cycle",
            sa.String(10),
            nullable=False,
            server_default="monthly",
            comment="결제 주기 (monthly/yearly)",
        ),
        # 구독 상태
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
            comment="구독 상태 (active/cancelled/past_due/expired)",
        ),
        # 월 결제 금액
        sa.Column(
            "amount",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="월 결제 금액 (원 단위)",
        ),
        # 구독 시작일
        sa.Column(
            "started_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            comment="구독 시작 시각 (UTC)",
        ),
        # 다음 결제일 (nullable)
        sa.Column(
            "next_billing_at",
            sa.DateTime(),
            nullable=True,
            comment="다음 결제 예정일 (UTC)",
        ),
        # 취소일 (nullable)
        sa.Column(
            "cancelled_at",
            sa.DateTime(),
            nullable=True,
            comment="구독 취소 시각 (UTC)",
        ),
        # 생성/수정 시각
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            comment="생성 시각 (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            comment="수정 시각 (UTC)",
        ),
    )

    # subscriptions 인덱스
    op.create_index("ix_subscriptions_workspace_id", "subscriptions", ["workspace_id"])
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"])
    # 워크스페이스별 활성 구독 조회를 위한 복합 인덱스
    op.create_index(
        "ix_subscriptions_workspace_status",
        "subscriptions",
        ["workspace_id", "status"],
    )

    # ── 2. billing_histories 테이블 생성 ──────────────────────
    op.create_table(
        "billing_histories",
        # PK
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="결제 내역 고유 식별자 (UUID v4)",
        ),
        # 워크스페이스 FK
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            comment="워크스페이스 FK",
        ),
        # 구독 FK (nullable)
        sa.Column(
            "subscription_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("subscriptions.id", ondelete="SET NULL"),
            nullable=True,
            comment="연관 구독 FK (nullable)",
        ),
        # 내역 타입
        sa.Column(
            "type",
            sa.String(20),
            nullable=False,
            comment="내역 타입 (subscription/upgrade/downgrade/refund)",
        ),
        # 플랜명
        sa.Column(
            "plan",
            sa.String(20),
            nullable=False,
            comment="대상 플랜명",
        ),
        # 결제 주기
        sa.Column(
            "billing_cycle",
            sa.String(10),
            nullable=False,
            server_default="monthly",
            comment="결제 주기 (monthly/yearly)",
        ),
        # 결제 금액
        sa.Column(
            "amount",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="결제 금액 (원 단위)",
        ),
        # 결제 상태
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="paid",
            comment="결제 상태 (paid/failed/refunded)",
        ),
        # PG 트랜잭션 ID
        sa.Column(
            "pg_transaction_id",
            sa.String(100),
            nullable=True,
            comment="PG 트랜잭션 ID (Mock 포함)",
        ),
        # 설명
        sa.Column(
            "description",
            sa.String(200),
            nullable=False,
            server_default="",
            comment="결제 내역 설명",
        ),
        # 생성 시각
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            comment="결제 처리 시각 (UTC)",
        ),
        # 수정 시각 (BaseModel 상속)
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            comment="수정 시각 (UTC)",
        ),
    )

    # billing_histories 인덱스
    op.create_index("ix_billing_histories_workspace_id", "billing_histories", ["workspace_id"])
    op.create_index("ix_billing_histories_subscription_id", "billing_histories", ["subscription_id"])
    op.create_index("ix_billing_histories_type", "billing_histories", ["type"])
    op.create_index("ix_billing_histories_status", "billing_histories", ["status"])
    op.create_index("ix_billing_histories_created_at", "billing_histories", ["created_at"])

    # ── 3. workspaces 테이블에 payment_method JSON 컬럼 추가 ──
    op.add_column(
        "workspaces",
        sa.Column(
            "payment_method",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
            comment="결제 수단 정보 (카드 last4, 브랜드, 유효기간 등 JSON)",
        ),
    )


def downgrade() -> None:
    """
    Sprint 8에서 추가된 테이블과 컬럼을 삭제합니다.
    """
    # workspaces payment_method 컬럼 삭제
    op.drop_column("workspaces", "payment_method")

    # billing_histories 테이블 삭제
    op.drop_index("ix_billing_histories_created_at", table_name="billing_histories")
    op.drop_index("ix_billing_histories_status", table_name="billing_histories")
    op.drop_index("ix_billing_histories_type", table_name="billing_histories")
    op.drop_index("ix_billing_histories_subscription_id", table_name="billing_histories")
    op.drop_index("ix_billing_histories_workspace_id", table_name="billing_histories")
    op.drop_table("billing_histories")

    # subscriptions 테이블 삭제
    op.drop_index("ix_subscriptions_workspace_status", table_name="subscriptions")
    op.drop_index("ix_subscriptions_status", table_name="subscriptions")
    op.drop_index("ix_subscriptions_workspace_id", table_name="subscriptions")
    op.drop_table("subscriptions")
