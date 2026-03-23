"""
Alembic 마이그레이션: 006_add_settlements
Sprint 9: 정산 관리 테이블 생성

  settlements       — 미디어사 월별 정산 헤더
  settlement_items  — 정산 상세 항목 (주문별)

Revision ID: 006
Revises: 005
Create Date: 2026-03-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# ── 마이그레이션 메타데이터 ─────────────────────────────────
revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    1. settlements 테이블 생성
    2. settlement_items 테이블 생성
    """

    # ── 1. settlements 테이블 생성 ─────────────────────────────
    op.create_table(
        "settlements",
        # PK
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="정산 고유 식별자 (UUID v4)",
        ),
        # FK: 미디어사
        sa.Column(
            "media_company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("media_companies.id", ondelete="CASCADE"),
            nullable=False,
            comment="미디어사 FK",
        ),
        # 정산 월 (YYYY-MM)
        sa.Column(
            "month",
            sa.String(7),
            nullable=False,
            comment="정산 대상 월 (예: 2026-03)",
        ),
        # 정산 상태
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            comment="정산 상태 (pending/approved/paid)",
        ),
        # 집계 정보
        sa.Column(
            "total_orders",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="총 주문 건수",
        ),
        sa.Column(
            "total_amount",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="총 주문 금액 (원 단위)",
        ),
        # 수수료 정보
        sa.Column(
            "commission_rate",
            sa.Float(),
            nullable=False,
            server_default="0.7",
            comment="미디어사 수취 비율 (예: 0.7 = 70%)",
        ),
        sa.Column(
            "commission_amount",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="실제 지급액 = round(total_amount * commission_rate)",
        ),
        # 처리 일시
        sa.Column(
            "approved_at",
            sa.DateTime(),
            nullable=True,
            comment="승인 시각 (UTC)",
        ),
        sa.Column(
            "paid_at",
            sa.DateTime(),
            nullable=True,
            comment="지급 완료 시각 (UTC)",
        ),
        # 생성/수정 시각
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
            comment="생성 시각 (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
            comment="수정 시각 (UTC)",
        ),
        comment="미디어사 월별 정산 헤더",
    )

    # settlements 인덱스
    op.create_index(
        "ix_settlements_media_company_id",
        "settlements",
        ["media_company_id"],
    )
    op.create_index(
        "ix_settlements_month",
        "settlements",
        ["month"],
    )
    op.create_index(
        "ix_settlements_status",
        "settlements",
        ["status"],
    )
    # 동일 미디어사 + 월 중복 방지 유니크 인덱스
    op.create_index(
        "uq_settlements_media_company_month",
        "settlements",
        ["media_company_id", "month"],
        unique=True,
    )

    # ── 2. settlement_items 테이블 생성 ────────────────────────
    op.create_table(
        "settlement_items",
        # PK
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="정산 항목 고유 식별자 (UUID v4)",
        ),
        # FK: 정산 헤더
        sa.Column(
            "settlement_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("settlements.id", ondelete="CASCADE"),
            nullable=False,
            comment="정산 헤더 FK",
        ),
        # FK: 주문
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
            comment="주문 FK",
        ),
        # 금액
        sa.Column(
            "amount",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="해당 주문 금액 (원 단위)",
        ),
        sa.Column(
            "commission_amount",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="해당 주문 지급액 = round(amount * commission_rate)",
        ),
        # 생성 시각
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
            comment="생성 시각 (UTC)",
        ),
        comment="정산 상세 항목 (주문별)",
    )

    # settlement_items 인덱스
    op.create_index(
        "ix_settlement_items_settlement_id",
        "settlement_items",
        ["settlement_id"],
    )
    op.create_index(
        "ix_settlement_items_order_id",
        "settlement_items",
        ["order_id"],
    )
    # 한 주문은 하나의 정산 아이템에만 포함 (중복 방지)
    op.create_index(
        "uq_settlement_items_order_id",
        "settlement_items",
        ["order_id"],
        unique=True,
    )


def downgrade() -> None:
    """
    settlement_items → settlements 순서로 DROP
    (FK 참조 순서에 맞게 역순)
    """
    # settlement_items 인덱스 삭제
    op.drop_index("uq_settlement_items_order_id", table_name="settlement_items")
    op.drop_index("ix_settlement_items_order_id", table_name="settlement_items")
    op.drop_index("ix_settlement_items_settlement_id", table_name="settlement_items")
    op.drop_table("settlement_items")

    # settlements 인덱스 삭제
    op.drop_index("uq_settlements_media_company_month", table_name="settlements")
    op.drop_index("ix_settlements_status", table_name="settlements")
    op.drop_index("ix_settlements_month", table_name="settlements")
    op.drop_index("ix_settlements_media_company_id", table_name="settlements")
    op.drop_table("settlements")
