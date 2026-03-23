"""
nplace.io 파서 API 서버 v3.0
================================
naver_place_parser.py v5.0을 REST API로 노출.
asyncio 병렬 파싱, GraphQL 페이지네이션, 모든 탭(영수증리뷰/블로그리뷰/영업시간/편의시설/사진) 지원.

엔드포인트
----------
GET  /                         헬스체크
POST /api/parse                URL/ID 파싱 → 전체 정보 반환
GET  /api/parse/{place_id}     place_id 직접 파싱 (category 쿼리파라미터)
POST /api/parse/preview        빠른 미리보기 (홈 탭만, 기본정보+리뷰수)
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
