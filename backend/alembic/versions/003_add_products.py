"""
003_add_products_and_order_columns

product_types, products 테이블 추가 및
orders 테이블에 Sprint 5 신규 컬럼 추가.

Revision ID: 003
Revises: 002
Create Date: 2026-03-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Alembic revision 식별자
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """product_types, products 테이블 생성 및 orders 컬럼 추가"""

    # ── 1. product_types 테이블 생성 ─────────────────────────
    op.create_table(
        "product_types",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="기본 키 (UUID v4)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(100),
            nullable=False,
            comment="상품 유형명",
        ),
        sa.Column(
            "description",
            sa.String(500),
            nullable=True,
            comment="유형 설명",
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default="true",
            comment="활성화 상태",
        ),
        sa.Column(
            "sort_order",
            sa.Integer,
            nullable=False,
            server_default="0",
            comment="정렬 순서",
        ),
        sa.UniqueConstraint("name", name="uq_product_types_name"),
        comment="상품 유형 분류",
    )

    # ── 2. products 테이블 생성 ──────────────────────────────
    op.create_table(
        "products",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="기본 키 (UUID v4)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "product_type_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_types.id", ondelete="CASCADE"),
            nullable=False,
            comment="상품 유형 FK",
        ),
        sa.Column(
            "name",
            sa.String(200),
            nullable=False,
            comment="상품명",
        ),
        sa.Column(
            "description",
            sa.String(1000),
            nullable=True,
            comment="상품 설명",
        ),
        sa.Column(
            "base_price",
            sa.Integer,
            nullable=False,
            comment="기본 가격 (원 단위)",
        ),
        sa.Column(
            "unit",
            sa.String(50),
            nullable=False,
            server_default="'건'",
            comment="수량 단위",
        ),
        sa.Column(
            "min_quantity",
            sa.Integer,
            nullable=False,
            server_default="1",
            comment="최소 주문 수량",
        ),
        sa.Column(
            "max_quantity",
            sa.Integer,
            nullable=True,
            comment="최대 주문 수량",
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default="true",
            comment="판매 중 여부",
        ),
        sa.Column(
            "sort_order",
            sa.Integer,
            nullable=False,
            server_default="0",
            comment="정렬 순서",
        ),
        sa.Column(
            "extra_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="추가 정보 (badge, features 등)",
        ),
        comment="판매 상품 목록",
    )

    # products 인덱스
    op.create_index("idx_products_product_type_id", "products", ["product_type_id"])
    op.create_index("idx_products_is_active", "products", ["is_active"])

    # ── 3. orders 테이블에 신규 컬럼 추가 ──────────────────────
    # product_id FK
    op.add_column(
        "orders",
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="SET NULL"),
            nullable=True,
            comment="주문 상품 FK",
        ),
    )
    op.create_index("idx_orders_product_id", "orders", ["product_id"])

    # keyword_ids (선택된 키워드 UUID 목록)
    op.add_column(
        "orders",
        sa.Column(
            "keyword_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="선택된 키워드 UUID 목록",
        ),
    )

    # quantity (주문 수량)
    op.add_column(
        "orders",
        sa.Column(
            "quantity",
            sa.Integer,
            nullable=False,
            server_default="1",
            comment="주문 수량",
        ),
    )

    # unit_price (단가)
    op.add_column(
        "orders",
        sa.Column(
            "unit_price",
            sa.Integer,
            nullable=False,
            server_default="0",
            comment="단가 (원 단위)",
        ),
    )

    # special_requests (특이사항)
    op.add_column(
        "orders",
        sa.Column(
            "special_requests",
            sa.Text,
            nullable=True,
            comment="특이사항 / 요청사항",
        ),
    )


def downgrade() -> None:
    """Sprint 5 변경 사항 롤백"""

    # orders 신규 컬럼 제거
    op.drop_column("orders", "special_requests")
    op.drop_column("orders", "unit_price")
    op.drop_column("orders", "quantity")
    op.drop_column("orders", "keyword_ids")
    op.drop_index("idx_orders_product_id", table_name="orders")
    op.drop_column("orders", "product_id")

    # products 인덱스 및 테이블 제거
    op.drop_index("idx_products_is_active", table_name="products")
    op.drop_index("idx_products_product_type_id", table_name="products")
    op.drop_table("products")

    # product_types 테이블 제거
    op.drop_table("product_types")
