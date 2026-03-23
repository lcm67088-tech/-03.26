"""007 - Order 모델에 category, daily_qty, start_date, end_date 추가

Sprint 12: 주문 카테고리 및 작업 일정 필드 추가
- category: 주문 카테고리 enum (blog/reward_traffic/reward_save/receipt/sns)
- daily_qty: 일 수량 (트래픽·저장 등 일별 작업 단위)
- start_date: 작업 시작일 (DATE)
- end_date:   작업 종료일 (DATE)

Revision ID: 007
Revises: 006
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. OrderCategory enum 타입 생성
    order_category = postgresql.ENUM(
        "blog", "reward_traffic", "reward_save", "receipt", "sns",
        name="ordercategory",
        create_type=True,
    )
    order_category.create(op.get_bind(), checkfirst=True)

    # 2. orders 테이블에 컬럼 추가
    op.add_column(
        "orders",
        sa.Column(
            "category",
            postgresql.ENUM(
                "blog", "reward_traffic", "reward_save", "receipt", "sns",
                name="ordercategory",
                create_type=False,
            ),
            nullable=True,
            comment="주문 카테고리",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "daily_qty",
            sa.Integer(),
            nullable=True,
            comment="일 수량 (예: 저장하기 200/일)",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "start_date",
            sa.Date(),
            nullable=True,
            comment="작업 시작일",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "end_date",
            sa.Date(),
            nullable=True,
            comment="작업 종료일",
        ),
    )

    # 3. category 인덱스
    op.create_index("ix_orders_category", "orders", ["category"])
    op.create_index("ix_orders_start_date", "orders", ["start_date"])


def downgrade() -> None:
    op.drop_index("ix_orders_start_date", table_name="orders")
    op.drop_index("ix_orders_category", table_name="orders")
    op.drop_column("orders", "end_date")
    op.drop_column("orders", "start_date")
    op.drop_column("orders", "daily_qty")
    op.drop_column("orders", "category")

    # enum 타입 제거
    postgresql.ENUM(name="ordercategory").drop(op.get_bind(), checkfirst=True)
