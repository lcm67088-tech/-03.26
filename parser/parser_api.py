"""
nplace.io 파서 API 서버 v3.1
================================
naver_place_parser.py v5.0을 REST API로 노출.
asyncio 병렬 파싱, GraphQL 페이지네이션, 모든 탭(영수증리뷰/블로그리뷰/영업시간/편의시설/사진) 지원.

엔드포인트
----------
GET  /                         헬스체크
POST /api/parse                URL/ID 파싱 → 전체 정보 반환
GET  /api/parse/{place_id}     place_id 직접 파싱 (category 쿼리파라미터)
POST /api/parse/preview        빠른 미리보기 (홈 탭만, 기본정보+리뷰수)
POST /api/search-rank          키워드 순위 실측 (작업 키워드 찾기 전용)
"""

import sys
import os
import asyncio

# naver_place_parser.py 절대경로로 추가 (uvicorn 실행 시 __file__ 기준이 달라질 수 있음)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# parser/ 폴더 자체가 파서의 위치
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import re

# 파서 import
try:
    from naver_place_parser import (
        parse_place,
        parse_place_async,
        _extract_apollo,
        _parse_base,
        _parse_keyword_list,
        _parse_themes,
        _parse_description,
        _parse_static_map_url,
        _parse_review_counts,
        _tab_url,
    )
    import httpx as _httpx
    PARSER_AVAILABLE = True
    _import_error = ""
except ImportError as e:
    PARSER_AVAILABLE = False
    _import_error = str(e)

app = FastAPI(
    title="nplace.io 파서 API",
    description="네이버 플레이스 정보 파싱 API v3.0 (asyncio 병렬 + GraphQL 페이지네이션)",
    version="3.0.0",
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────

_PLACE_ID_PATTERNS = [
    r'map\.naver\.com/(?:v5|p)/entry/place/(\d+)',
    r'(?:m\.)?place\.naver\.com/[^/?#]+/(\d+)',
    r'place\.naver\.com/(\d+)(?:[/?#]|$)',
]
_CATEGORY_PATTERN = r'(?:m\.)?place\.naver\.com/([^/?#]+)/\d+'

_CATEGORY_MAP = {
    "restaurant": "restaurant", "cafe": "cafe",
    "accommodation": "accommodation", "hairshop": "hairshop",
    "nailshop": "nailshop", "hospital": "hospital",
    "place": "place", "beauty": "hairshop", "pharmacy": "hospital",
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://m.place.naver.com/",
}


def _extract_place_id(url: str) -> Optional[str]:
    s = url.strip()
    if s.isdigit():
        return s
    for pat in _PLACE_ID_PATTERNS:
        m = re.search(pat, s)
        if m:
            return m.group(1)
    return None


def _extract_category(url: str) -> Optional[str]:
    m = re.search(_CATEGORY_PATTERN, url)
    if m:
        return _CATEGORY_MAP.get(m.group(1), "restaurant")
    return None


# ─────────────────────────────────────────────
# 요청/응답 스키마
# ─────────────────────────────────────────────

class ParseRequest(BaseModel):
    url: str
    category: Optional[str] = None
    delay: float = 0.3
    fetch_blog_content: bool = False  # 블로그 원문 크롤링 여부
    max_visitor_reviews: int = 50      # 최대 영수증 리뷰 수
    max_blog_reviews: int = 50         # 최대 블로그 리뷰 수
    max_photos: int = 200              # 최대 사진 수


class PreviewRequest(BaseModel):
    url: str
    category: Optional[str] = None


# ─────────────────────────────────────────────
# 엔드포인트
# ─────────────────────────────────────────────

@app.get("/")
def health_check():
    return {
        "status": "ok",
        "service": "nplace.io 파서 API",
        "parser_available": PARSER_AVAILABLE,
        "version": "3.0.0",
        "features": [
            "영수증리뷰 최대 100건 (GraphQL 멀티소스)",
            "블로그리뷰 최대 100건 (GraphQL page 페이지네이션)",
            "영업시간 (브레이크/라스트오더 포함)",
            "편의시설 (InformationFacilities 포함)",
            "사진 최대 200장 (sasImages/ugcModeling/cpImages 멀티소스)",
            "asyncio 병렬 파싱",
            "업종별 완전 지원 (restaurant/cafe/hairshop/hospital/nailshop/place/accommodation)",
        ],
    }


@app.post("/api/parse")
async def parse_by_url(req: ParseRequest):
    """
    네이버 플레이스 전체 정보 파싱 (병렬).
    - 영수증 리뷰 20건 (이미지 포함)
    - 블로그 리뷰 10건 (썸네일 전체)
    - 영업시간 / 편의시설 / 사진 30장
    - 소요시간: 약 2~5초
    """
    if not PARSER_AVAILABLE:
        raise HTTPException(500, f"파서 모듈 로드 실패: {_import_error}")

    place_id = _extract_place_id(req.url)
    if not place_id:
        raise HTTPException(400, f"유효한 네이버 플레이스 URL/ID가 아닙니다: {req.url}")

    category = req.category or _extract_category(req.url) or "restaurant"

    try:
        result = await parse_place_async(
            place_id,
            category=category,
            delay=req.delay,
            fetch_blog_content=req.fetch_blog_content,
            max_visitor_reviews=req.max_visitor_reviews,
            max_blog_reviews=req.max_blog_reviews,
            max_photos=req.max_photos,
        )
    except Exception as e:
        raise HTTPException(502, f"파싱 실패: {e}")

    if result.get("error") and not result.get("name"):
        raise HTTPException(502, f"파싱 실패: {result['error']}")

    return {
        "success":  True,
        "place_id": place_id,
        "category": category,
        "data":     result,
    }


@app.get("/api/parse/{place_id}")
async def parse_by_id(
    place_id: str,
    category: str = Query("restaurant"),
    delay: float = Query(0.3),
    fetch_blog_content: bool = Query(False),
    max_visitor_reviews: int = Query(50),
    max_blog_reviews: int = Query(50),
    max_photos: int = Query(200),
):
    """place_id로 직접 파싱"""
    if not PARSER_AVAILABLE:
        raise HTTPException(500, f"파서 모듈 로드 실패: {_import_error}")
    if not place_id.isdigit():
        raise HTTPException(400, "place_id는 숫자여야 합니다")

    try:
        result = await parse_place_async(
            place_id, category=category, delay=delay,
            fetch_blog_content=fetch_blog_content,
            max_visitor_reviews=max_visitor_reviews,
            max_blog_reviews=max_blog_reviews,
            max_photos=max_photos,
        )
    except Exception as e:
        raise HTTPException(502, f"파싱 실패: {e}")

    if result.get("error") and not result.get("name"):
        raise HTTPException(502, f"파싱 실패: {result['error']}")

    return {"success": True, "place_id": place_id, "category": category, "data": result}


@app.post("/api/parse/preview")
async def parse_preview(req: PreviewRequest):
    """
    빠른 미리보기 - 홈 탭만 파싱 (기본정보 + 리뷰수).
    장소 등록 전 확인용. 소요시간: 약 1~2초.
    """
    if not PARSER_AVAILABLE:
        raise HTTPException(500, f"파서 모듈 로드 실패: {_import_error}")

    place_id = _extract_place_id(req.url)
    if not place_id:
        raise HTTPException(400, f"유효한 네이버 플레이스 URL/ID가 아닙니다: {req.url}")

    category = req.category or _extract_category(req.url) or "restaurant"

    try:
        home_url = _tab_url(place_id, category, "home")
        async with _httpx.AsyncClient(headers=_HEADERS, follow_redirects=True, timeout=20.0) as c:
            resp = await c.get(home_url)
            resp.raise_for_status()
            html = resp.text

        apollo_home = _extract_apollo(html)
        if not apollo_home:
            raise HTTPException(502, "페이지에서 데이터를 찾을 수 없습니다")

        base = _parse_base(apollo_home, place_id)
        # review 탭 없이 home에서만 리뷰수 추출
        counts = _parse_review_counts(apollo_home, {}, {}, place_id)

        preview = {
            **base,
            "keyword_list":   _parse_keyword_list(html),
            "themes":         _parse_themes(apollo_home),
            "introduction":   _parse_description(apollo_home),
            "static_map_url": _parse_static_map_url(apollo_home),
            "url":            f"https://m.place.naver.com/{category}/{place_id}",
            **counts,
        }

        return {
            "success":  True,
            "place_id": place_id,
            "category": category,
            "data":     preview,
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(502, f"미리보기 파싱 실패: {e}\n{traceback.format_exc()[:500]}")


# ─────────────────────────────────────────────
# 작업 키워드 찾기 — 순위 실측 엔드포인트
# ─────────────────────────────────────────────

class SearchRankRequest(BaseModel):
    keyword: str
    place_id: Optional[str] = None   # 네이버 플레이스 ID (숫자)
    max_rank: int = 5                 # 판정 기준 순위 (기본 5위)
    category: str = "restaurant"


@app.post("/api/search-rank")
async def search_rank(req: SearchRankRequest):
    """
    네이버 모바일 검색에서 키워드 순위를 실측합니다.
    
    반환값:
      - has_section : 플레이스 섹션 존재 여부
      - rank        : 플레이스 섹션 내 순위 (없으면 null)
      - is_top      : 플레이스 섹션이 검색 최상단 여부
      - has_cpc     : CPC 광고 존재 여부
      - is_single   : 업체 수 == 1 and rank == 1 (단일 키워드)
    """
    keyword_encoded = req.keyword.replace(" ", "+")
    search_url = f"https://m.search.naver.com/search.naver?query={keyword_encoded}&where=m"

    try:
        async with _httpx.AsyncClient(
            headers={**_HEADERS, "Referer": "https://m.search.naver.com/"},
            follow_redirects=True,
            timeout=15.0,
        ) as client:
            resp = await client.get(search_url)
            resp.raise_for_status()
            html = resp.text

        result = _parse_search_rank(html, req.place_id, req.max_rank)
        return {"success": True, "keyword": req.keyword, **result}

    except Exception as e:
        # 파싱 실패 시 기본값 반환 (탈락 처리)
        return {
            "success": False,
            "keyword": req.keyword,
            "error": str(e),
            "has_section": False,
            "rank": None,
            "is_top": False,
            "has_cpc": False,
            "is_single": False,
        }


def _parse_search_rank(html: str, place_id: Optional[str], max_rank: int) -> dict:
    """
    네이버 모바일 검색 HTML에서 플레이스 섹션 정보를 파싱합니다.
    
    판정 기준:
      1. 플레이스 섹션 존재 여부 (has_section)
      2. 순위 (rank): place_id 기반 위치 탐색, 없으면 null
      3. 최상단 여부 (is_top): 플레이스 섹션 위치가 검색 결과 상단
      4. CPC 여부 (has_cpc): 광고 배지 탐색
      5. 단일 여부 (is_single): 업체수 1 and rank 1
    """
    import re as _re

    # ── 1. 플레이스 섹션 존재 여부 ──
    # 네이버 모바일 검색에서 플레이스 섹션은 class에 'place_area' 또는 data-nclick에 'plc' 포함
    section_patterns = [
        r'class="[^"]*place_area[^"]*"',
        r'data-nclick="[^"]*plc\.[^"]*"',
        r'id="place-main-section"',
        r'"type":"place"',
        r'class="[^"]*ct_local[^"]*"',   # 로컬 탭 내 플레이스
        r'spf=1.*?place',
        r'class="[^"]*_PlaceSection[^"]*"',
        r'place\.naver\.com',             # 플레이스 링크 존재
    ]
    has_section = any(_re.search(p, html, _re.IGNORECASE) for p in section_patterns)

    if not has_section:
        return {"has_section": False, "rank": None, "is_top": False, "has_cpc": False, "is_single": False}

    # ── 2. CPC 여부 ──
    cpc_patterns = [
        r'class="[^"]*ad_area[^"]*"',
        r'class="[^"]*_cpc[^"]*"',
        r'"isAd"\s*:\s*true',
        r'광고</span>',
        r'class="[^"]*place_ad[^"]*"',
        r'ad_marker',
    ]
    has_cpc = any(_re.search(p, html, _re.IGNORECASE) for p in cpc_patterns)

    # ── 3. 최상단 여부 ──
    # 검색 결과 HTML에서 플레이스 섹션이 VIEW/웹 섹션 이전에 나오는지 확인
    place_pos = -1
    view_pos  = -1
    for p in [r'place_area', r'_PlaceSection', r'ct_local', r'place\.naver\.com/']:
        m = _re.search(p, html, _re.IGNORECASE)
        if m and (place_pos == -1 or m.start() < place_pos):
            place_pos = m.start()

    view_patterns = [r'class="[^"]*view_area[^"]*"', r'class="[^"]*blog_area[^"]*"', r'class="[^"]*web_area[^"]*"']
    for p in view_patterns:
        m = _re.search(p, html, _re.IGNORECASE)
        if m and (view_pos == -1 or m.start() < view_pos):
            view_pos = m.start()

    # 플레이스가 먼저 나오거나 view 섹션이 없으면 최상단
    is_top = (place_pos != -1) and (view_pos == -1 or place_pos < view_pos)

    # ── 4. 순위 및 단일 여부 ──
    rank = None
    is_single = False

    if place_id:
        # place_id로 플레이스 링크 위치 탐색
        place_links = _re.findall(
            r'place\.naver\.com/[^/]+/(\d+)',
            html, _re.IGNORECASE
        )
        # 중복 제거 (순서 유지)
        seen = []
        for pid in place_links:
            if pid not in seen:
                seen.append(pid)
        place_links_unique = seen

        if place_id in place_links_unique:
            rank = place_links_unique.index(place_id) + 1
            total_places = len(place_links_unique)
            is_single = (rank == 1 and total_places == 1)
        # place_id 없어도 섹션은 있음 → rank = null
    else:
        # place_id 미제공 시 섹션 내 첫 번째 순위 수집만
        all_links = _re.findall(r'place\.naver\.com/[^/]+/(\d+)', html)
        if all_links:
            rank = 1  # 최소 1개 이상 있으면 섹션 내 업체 존재

    return {
        "has_section": has_section,
        "rank":        rank,
        "is_top":      is_top,
        "has_cpc":     has_cpc,
        "is_single":   is_single,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
