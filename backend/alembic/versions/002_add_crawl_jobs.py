"""
002_add_crawl_jobs

crawl_jobs 테이블 및 관련 인덱스 추가 (Sprint 4)

Revision ID: 002
Revises: 001
Create Date: 2026-03-18 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Alembic revision 식별자
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """crawl_jobs 테이블 생성"""

    # CrawlJobStatus ENUM 타입 생성 (IF NOT EXISTS 패턴)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'crawljobstatus') THEN
                CREATE TYPE crawljobstatus AS ENUM ('queued', 'running', 'done', 'failed');
            END IF;
        END $$;
    """)

    # crawl_jobs 테이블 생성
    op.create_table(
        "crawl_jobs",
        # ── 기본 키 / 타임스탬프 (BaseModel 공통) ──────────────
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
            comment="생성 시간",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="수정 시간",
        ),
        # ── 핵심 컬럼 ──────────────────────────────────────────
        sa.Column(
            "keyword_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("place_keywords.id", ondelete="CASCADE"),
            nullable=False,
            comment="대상 키워드 FK",
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "queued", "running", "done", "failed",
                name="crawljobstatus",
                create_type=False,   # 위 DO $$ 블록에서 이미 생성함
            ),
            nullable=False,
            server_default="queued",
            comment="잡 상태",
        ),
        sa.Column(
            "scheduled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="실행 예약 시각",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="실행 시작 시각",
        ),
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="실행 완료 시각",
        ),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="크롤링 결과 JSON",
        ),
        sa.Column(
            "retry_count",
            sa.Integer,
            nullable=False,
            server_default="0",
            comment="재시도 횟수",
        ),
        comment="크롤링 작업 큐 테이블",
    )

    # ── 인덱스 ────────────────────────────────────────────────
    # 스케줄러: status + scheduled_at 조회 최적화
    op.create_index(
        "idx_crawl_jobs_status_scheduled",
        "crawl_jobs",
        ["status", "scheduled_at"],
    )
    # 키워드별 잡 목록 조회 최적화
    op.create_index(
        "idx_crawl_jobs_keyword_id",
        "crawl_jobs",
        ["keyword_id"],
    )
    # status 단독 인덱스 (빠른 상태별 필터링)
    op.create_index(
        "idx_crawl_jobs_status",
        "crawl_jobs",
        ["status"],
    )


def downgrade() -> None:
    """crawl_jobs 테이블 및 인덱스 삭제"""
    op.drop_index("idx_crawl_jobs_status", table_name="crawl_jobs")
    op.drop_index("idx_crawl_jobs_keyword_id", table_name="crawl_jobs")
    op.drop_index("idx_crawl_jobs_status_scheduled", table_name="crawl_jobs")
    op.drop_table("crawl_jobs")
    op.execute("DROP TYPE crawljobstatus")
