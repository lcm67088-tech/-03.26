"""
장소(Place) 관련 Pydantic 스키마 (Sprint 3 완성)

PlaceCreate, PlaceUpdate, PlaceListItem, PlaceDetail,
KeywordSummary, DashboardSummary 등 포함.
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator


# ============================
# 요청 스키마
# ============================

class PlaceCreate(BaseModel):
    """장소 등록 요청"""
    workspace_id: str
    naver_place_url: str
    alias: Optional[str] = None

    @field_validator("naver_place_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """URL 기본 형식 검증"""
        v = v.strip()
        if not v.startswith("http"):
            raise ValueError("올바른 URL 형식이 아닙니다")
        return v

    @field_validator("alias")
    @classmethod
    def validate_alias(cls, v: Optional[str]) -> Optional[str]:
        """별칭 길이 검증"""
        if v is not None:
            v = v.strip()
            if len(v) > 50:
                raise ValueError("별칭은 50자 이하여야 합니다")
            if len(v) == 0:
                return None
        return v


class PlaceUpdate(BaseModel):
    """장소 수정 요청 (alias, is_active만 수정 가능)"""
    alias: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("alias")
    @classmethod
    def validate_alias(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) > 50:
                raise ValueError("별칭은 50자 이하여야 합니다")
        return v


# ============================
# 응답 서브스키마
# ============================

class KeywordSummary(BaseModel):
    """키워드 + 최신 순위 요약 (장소 응답에 포함)"""
    id: str
    keyword: str
    is_primary: bool
    is_active: bool
    group_name: Optional[str] = None
    latest_rank: Optional[int] = None       # 최신 순위 (None = 미진입)
    case_type: Optional[str] = None         # normal | popular | not_ranked
    rank_change: Optional[int] = None       # 어제 대비 변화 (+3, -2, 0)

    model_config = {"from_attributes": True}


class PlaceListItem(BaseModel):
    """장소 목록 아이템"""
    id: str
    naver_place_id: str
    naver_place_url: str
    name: str
    alias: Optional[str] = None
    category: Optional[str] = None
    is_active: bool
    keyword_count: int = 0
    latest_rankings: list[KeywordSummary] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class PlaceDetail(BaseModel):
    """장소 상세 응답"""
    id: str
    naver_place_id: str
    naver_place_url: str
    name: str
    alias: Optional[str] = None
    category: Optional[str] = None
    address: Optional[str] = None
    is_active: bool
    keyword_count: int = 0
    keywords: list[KeywordSummary] = []
    recent_orders: list[dict[str, Any]] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================
# 대시보드 응답 스키마
# ============================

class RankSummaryKeyword(BaseModel):
    """대시보드 순위 요약 내 키워드"""
    keyword: str
    rank: Optional[int] = None
    case_type: Optional[str] = None
    rank_change: Optional[int] = None


class PlaceRankSummary(BaseModel):
    """대시보드 장소별 순위 요약"""
    place_id: str
    place_name: str
    alias: Optional[str] = None
    keywords: list[RankSummaryKeyword] = []


class RecentOrderItem(BaseModel):
    """대시보드 최근 주문 아이템"""
    id: str
    product_name: str
    status: str
    total_amount: int
    ordered_at: Optional[datetime] = None


class DashboardSummary(BaseModel):
    """대시보드 요약 응답"""
    total_places: int
    total_keywords: int
    this_month_orders: int
    this_month_revenue: int         # 원 단위
    avg_rank: Optional[float]       # 전체 키워드 평균 순위 (None = 데이터 없음)
    rank_summary: list[PlaceRankSummary] = []
    recent_orders: list[RecentOrderItem] = []


# ============================
# 목록 응답 래퍼
# ============================

class PlaceListResponse(BaseModel):
    """장소 목록 응답 (페이지네이션)"""
    total: int
    items: list[PlaceListItem]
