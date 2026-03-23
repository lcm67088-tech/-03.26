"""
Keyword 및 KeywordRanking 모델
키워드 관리 및 순위 이력 추적
"""
import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class RankCaseType(str, enum.Enum):
    """
    순위 케이스 타입
    - normal: 일반 검색 결과
    - popular: 인기 상위 노출
    - not_ranked: 순위권 외 (보통 50위 이상)
    """
    NORMAL = "normal"
    POPULAR = "popular"
    NOT_RANKED = "not_ranked"


class PlaceKeyword(BaseModel):
    """
    플레이스-키워드 연결 테이블
    순위 모니터링 대상 키워드 관리
    
    Relations:
        - place: 소속 플레이스
        - rankings: 순위 이력
    """
    __tablename__ = "place_keywords"
    __table_args__ = {"comment": "플레이스 키워드 (순위 모니터링 대상)"}

    # 소속 플레이스
    place_id = Column(
        UUID(as_uuid=True),
        ForeignKey("places.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="플레이스 FK",
    )

    # 키워드 정보
    keyword = Column(
        String(200),
        nullable=False,
        comment="키워드 텍스트",
    )
    is_primary = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="대표 키워드 여부",
    )
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="키워드 활성화 상태",
    )
    group_name = Column(
        String(100),
        nullable=True,
        comment="키워드 그룹명",
    )

    # Relations
    place = relationship("Place", back_populates="keywords")
    rankings = relationship(
        "KeywordRanking",
        back_populates="keyword",
        cascade="all, delete-orphan",
        order_by="KeywordRanking.crawled_at.desc()",
    )

    def __repr__(self) -> str:
        return f"<PlaceKeyword {self.keyword}>"


class KeywordRanking(BaseModel):
    """
    키워드 순위 이력 테이블
    크롤링으로 수집된 순위 데이터를 시계열로 저장
    
    이 테이블은 데이터가 매우 빠르게 쌓이므로
    파티셔닝 전략 필요 (crawled_at 기준 월별 파티션)
    """
    __tablename__ = "keyword_rankings"
    __table_args__ = {"comment": "키워드 순위 이력 (시계열 데이터)"}

    # 키워드
    keyword_id = Column(
        UUID(as_uuid=True),
        ForeignKey("place_keywords.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="플레이스 키워드 FK",
    )

    # 순위 정보
    rank = Column(
        Integer,
        nullable=True,
        comment="순위 (미진입 시 NULL)",
    )
    case_type = Column(
        Enum(RankCaseType),
        default=RankCaseType.NORMAL,
        nullable=False,
        comment="순위 케이스 타입",
    )

    # 크롤링 시간
    crawled_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="크롤링 수행 시간",
    )

    # 추가 데이터
    extra_data = Column(
        JSONB,
        nullable=True,
        default=dict,
        comment="추가 정보 (검색량, 경쟁사 순위 등)",
    )

    # Relations
    keyword = relationship("PlaceKeyword", back_populates="rankings")

    def __repr__(self) -> str:
        return f"<KeywordRanking keyword={self.keyword_id} rank={self.rank} at={self.crawled_at}>"
