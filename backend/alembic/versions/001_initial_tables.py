"""initial_tables

초기 데이터베이스 테이블 생성
- users
- workspaces
- workspace_members
- places
- place_keywords
- keyword_rankings
- media_companies
- orders
- payments

Revision ID: 001
Revises: 
Create Date: 2026-03-18 00:00:00.000000

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =====================
    # ENUM 타입 생성
    # =====================
    # ENUM 타입 생성 (존재하지 않을 때만)
    enums = [
        ("userrole",      "'user', 'admin', 'superadmin'"),
        ("workspaceplan", "'free', 'starter', 'pro', 'enterprise'"),
        ("memberrole",    "'owner', 'manager', 'viewer'"),
        ("rankcasetype",  "'normal', 'popular', 'not_ranked'"),
        ("orderstatus",   "'pending', 'confirmed', 'in_progress', 'completed', 'cancelled', 'refunded', 'disputed'"),
        ("paymentmethod", "'kakaopay', 'naverpay', 'card'"),
        ("paymentstatus", "'pending', 'completed', 'failed', 'refunded'"),
    ]
    for name, values in enums:
        op.execute(f"""
            DO $$ BEGIN
                CREATE TYPE {name} AS ENUM ({values});
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
        """)

    # =====================
    # users 테이블
    # =====================
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('role', postgresql.ENUM('user', 'admin', 'superadmin', name='userrole', create_type=False), nullable=False, server_default='user'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='uq_users_email'),
        comment='플랫폼 유저 계정'
    )
    op.create_index('ix_users_email', 'users', ['email'])

    # =====================
    # workspaces 테이블
    # =====================
    op.create_table(
        'workspaces',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('plan', postgresql.ENUM('free', 'starter', 'pro', 'enterprise', name='workspaceplan', create_type=False), nullable=False, server_default='free'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('extra_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        comment='워크스페이스 (에이전시/사업자 단위)'
    )
    op.create_index('ix_workspaces_owner_id', 'workspaces', ['owner_id'])

    # =====================
    # workspace_members 테이블
    # =====================
    op.create_table(
        'workspace_members',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', postgresql.ENUM('owner', 'manager', 'viewer', name='memberrole', create_type=False), nullable=False, server_default='viewer'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', 'user_id', name='uq_workspace_user'),
        comment='워크스페이스 멤버십'
    )
    op.create_index('ix_workspace_members_workspace_id', 'workspace_members', ['workspace_id'])
    op.create_index('ix_workspace_members_user_id', 'workspace_members', ['user_id'])

    # =====================
    # media_companies 테이블
    # =====================
    op.create_table(
        'media_companies',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('contact_email', sa.String(255), nullable=True),
        sa.Column('contact_phone', sa.String(20), nullable=True),
        sa.Column('bank_account', sa.String(200), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('extra_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        comment='매체사 (트래픽 집행 파트너사) - 어드민 전용'
    )

    # =====================
    # places 테이블
    # =====================
    op.create_table(
        'places',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('naver_place_id', sa.String(100), nullable=False),
        sa.Column('naver_place_url', sa.String(500), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('alias', sa.String(100), nullable=True),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('address', sa.String(300), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('extra_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        comment='네이버 플레이스 업체 정보'
    )
    op.create_index('ix_places_workspace_id', 'places', ['workspace_id'])
    op.create_index('ix_places_naver_place_id', 'places', ['naver_place_id'])

    # =====================
    # orders 테이블
    # =====================
    op.create_table(
        'orders',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('place_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('product_name', sa.String(200), nullable=False),
        sa.Column('description', sa.String(1000), nullable=True),
        sa.Column('total_amount', sa.Integer(), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'confirmed', 'in_progress', 'completed', 'cancelled', 'refunded', 'disputed', name='orderstatus', create_type=False), nullable=False, server_default='pending'),
        sa.Column('media_company_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('proof_url', sa.String(500), nullable=True),
        sa.Column('ordered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('extra_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['place_id'], ['places.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['media_company_id'], ['media_companies.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        comment='주문 정보'
    )
    op.create_index('ix_orders_workspace_id', 'orders', ['workspace_id'])
    op.create_index('ix_orders_status', 'orders', ['status'])
    op.create_index('ix_orders_place_id', 'orders', ['place_id'])

    # =====================
    # payments 테이블
    # =====================
    op.create_table(
        'payments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('method', postgresql.ENUM('kakaopay', 'naverpay', 'card', name='paymentmethod', create_type=False), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'completed', 'failed', 'refunded', name='paymentstatus', create_type=False), nullable=False, server_default='pending'),
        sa.Column('pg_transaction_id', sa.String(200), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('order_id', name='uq_payments_order_id'),
        sa.PrimaryKeyConstraint('id'),
        comment='결제 정보'
    )

    # =====================
    # place_keywords 테이블
    # =====================
    op.create_table(
        'place_keywords',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('place_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('keyword', sa.String(200), nullable=False),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('group_name', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['place_id'], ['places.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        comment='플레이스 키워드 (순위 모니터링 대상)'
    )
    op.create_index('ix_place_keywords_place_id', 'place_keywords', ['place_id'])

    # =====================
    # keyword_rankings 테이블
    # =====================
    op.create_table(
        'keyword_rankings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('keyword_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=True),
        sa.Column('case_type', postgresql.ENUM('normal', 'popular', 'not_ranked', name='rankcasetype', create_type=False), nullable=False, server_default='normal'),
        sa.Column('crawled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('extra_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['keyword_id'], ['place_keywords.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        comment='키워드 순위 이력 (시계열 데이터)'
    )
    op.create_index('ix_keyword_rankings_keyword_id', 'keyword_rankings', ['keyword_id'])
    op.create_index('ix_keyword_rankings_crawled_at', 'keyword_rankings', ['crawled_at'])


def downgrade() -> None:
    op.drop_table('keyword_rankings')
    op.drop_table('place_keywords')
    op.drop_table('payments')
    op.drop_table('orders')
    op.drop_table('places')
    op.drop_table('media_companies')
    op.drop_table('workspace_members')
    op.drop_table('workspaces')
    op.drop_table('users')

    # ENUM 타입 제거
    op.execute("DROP TYPE IF EXISTS paymentstatus")
    op.execute("DROP TYPE IF EXISTS paymentmethod")
    op.execute("DROP TYPE IF EXISTS orderstatus")
    op.execute("DROP TYPE IF EXISTS rankcasetype")
    op.execute("DROP TYPE IF EXISTS memberrole")
    op.execute("DROP TYPE IF EXISTS workspaceplan")
    op.execute("DROP TYPE IF EXISTS userrole")
