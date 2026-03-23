"""
CrawlJob 모델 (Sprint 4 신규)

크롤링 작업 큐 관리 테이블.
Celery 태스크가 이 테이블을 통해 작업 상태를 추적한다.

- status: queued → running → done | failed
- retry_count: 실패 시 최대 3회 재시도
- result: 크롤링 결과 JSON (rank, case_type, error)
"""
import enum
import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class CrawlJobStatus(str, enum.Enum):
    """크롤링 잡 상태"""
    QUEUED = "queued"       # 큐에 대기 중
    RUNNING = "running"     # 실행 중
    DONE = "done"           # 완료
    FAILED = "failed"       # 실패 (최대 재시도 초과)


class CrawlJob(BaseModel):
    """
    크롤링 작업 레코드.

    Celery 워커가 이 레코드를 읽어 크롤링을 실행하고
    완료 후 status / result 를 업데이트한다.
    """
    __tablename__ = "crawl_jobs"
    __table_args__ = (
        # 상태 + 예약시각 복합 인덱스 (스케줄러 쿼리 최적화)
        Index("idx_crawl_jobs_status_scheduled", "status", "scheduled_at"),
        # 키워드별 잡 조회 인덱스
        Index("idx_crawl_jobs_keyword_id", "keyword_id"),
        {"comment": "크롤링 작업 큐 테이블"},
    )

    # ── 연결 키워드 ──────────────────────────────────────────
    keyword_id = Column(
        UUID(as_uuid=True),
        ForeignKey("place_keywords.id", ondelete="CASCADE"),
        nullable=False,
        comment="대상 키워드 FK",
    )

    # ── 상태 관리 ─────────────────────────────────────────────
    status = Column(
        Enum(CrawlJobStatus, values_callable=lambda x: [e.value for e in x]),
        default=CrawlJobStatus.QUEUED,
        nullable=False,
        index=True,
        comment="잡 상태 (queued/running/done/failed)",
    )

    # ── 시간 기록 ─────────────────────────────────────────────
    scheduled_at = Column(
        DateTime(timezone=True),
        nullable=False,
        comment="실행 예약 시각",
    )
    started_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="실제 실행 시작 시각",
    )
    finished_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="실행 완료 시각",
    )

    # ── 결과 / 재시도 ─────────────────────────────────────────
    result = Column(
        JSONB,
        nullable=True,
        comment="크롤링 결과 JSON { rank, case_type, error }",
    )
    retry_count = Column(
        Integer,
        default=0,
        nullable=False,
        comment="재시도 횟수",
    )

    # ── Relations ────────────────────────────────────────────
    keyword = relationship("PlaceKeyword", backref="crawl_jobs")

    def __repr__(self) -> str:
        return f"<CrawlJob keyword={self.keyword_id} status={self.status}>"
