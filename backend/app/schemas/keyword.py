"""
키워드(Keyword) 관련 Pydantic 스키마 (Sprint 4 완성)

KeywordCreate, KeywordUpdate, KeywordWithRank,
RankingPoint, KeywordListResponse, RankingHistoryResponse 포함.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, field_validator


# ============================
# 요청 스키마
# ============================

class KeywordCreate(BaseModel):
    """키워드 등록 요청"""
    keyword: str
    is_primary: bool = False
    group_name: Optional[str] = None

    @field_validator("keyword")
    @classmethod
    def validate_keyword(cls, v: str) -> str:
        """키워드 길이 및 공백 검증"""
        v = v.strip()
        if not v:
            raise ValueError("키워드를 입력해주세요")
        if len(v) > 50:
            raise ValueError("키워드는 50자 이하여야 합니다")
        return v

    @field_validator("group_name")
    @classmethod
    def validate_group_name(cls, v: Optional[str]) -> Optional[str]:
        """그룹명 길이 검증"""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
            if len(v) > 50:
                raise ValueError("그룹명은 50자 이하여야 합니다")
        return v


class KeywordUpdate(BaseModel):
    """키워드 수정 요청"""
    is_primary: Optional[bool] = None
    group_name: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("group_name")
    @classmethod
    def validate_group_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
            if len(v) > 50:
                raise ValueError("그룹명은 50자 이하여야 합니다")
        return v


# ============================
# 응답 서브스키마
# ============================

class RankingPoint(BaseModel):
    """순위 이력 단일 데이터 포인트"""
    rank: Optional[int] = None          # 순위 (미진입 시 None)
    case_type: str                       # normal | popular | not_ranked
    crawled_at: datetime                 # 크롤링 시각

    model_config = {"from_attributes": True}


class KeywordWithRank(BaseModel):
    """키워드 + 최신 순위 + 통계 정보"""
    id: str
    keyword: str
    is_primary: bool
    group_name: Optional[str] = None
    is_active: bool
    latest_rank: Optional[int] = None       # 최신 순위 (None = 미진입 또는 미크롤링)
    case_type: Optional[str] = None         # normal | popular | not_ranked
    rank_change: Optional[int] = None       # 어제 대비 변동 (+n = 상승, -n = 하락)
    rank_7d_avg: Optional[float] = None     # 7일 평균 순위
    best_rank: Optional[int] = None         # 역대 최고 순위
    worst_rank: Optional[int] = None        # 역대 최저 순위
    crawled_at: Optional[datetime] = None   # 최신 크롤링 시각

    model_config = {"from_attributes": True}


# ============================
# 목록/이력 응답 래퍼
# ============================

class KeywordListResponse(BaseModel):
    """키워드 목록 응답"""
    total: int
    items: List[KeywordWithRank]


class RankingHistoryResponse(BaseModel):
    """특정 키워드의 순위 이력 응답"""
    keyword_id: str
    keyword: str
    period: str                             # 7d | 30d | 90d
    rankings: List[RankingPoint]


class PlaceRankingSummaryKeyword(BaseModel):
    """장소 전체 순위 요약 내 키워드 정보"""
    id: str
    keyword: str
    is_primary: bool
    group_name: Optional[str] = None
    latest_rank: Optional[int] = None
    case_type: Optional[str] = None
    crawled_at: Optional[datetime] = None
    rank_change: Optional[int] = None
    rank_7d_avg: Optional[float] = None
    best_rank: Optional[int] = None
    worst_rank: Optional[int] = None


class PlaceRankingSummaryResponse(BaseModel):
    """장소 전체 키워드 순위 요약 응답"""
    place_id: str
    place_name: str
    keywords: List[PlaceRankingSummaryKeyword]


# ============================
# 기존 스키마와의 호환성 유지
# ============================

class KeywordResponse(BaseModel):
    """
    기존 Sprint 2/3 호환용 단순 키워드 응답.
    Sprint 5 이후 KeywordWithRank로 통합 예정.
    """
    id: str
    place_id: str
    keyword: str
    is_primary: bool
    is_active: bool
    group_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RankingResponse(BaseModel):
    """순위 단건 응답 (기존 호환용)"""
    id: str
    keyword_id: str
    rank: Optional[int] = None
    case_type: str
    crawled_at: datetime
    extra_data: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}
