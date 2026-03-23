"""
workers/crawler/place_info.py
──────────────────────────────────────────────────────────────────────────────
네이버 플레이스 기본 정보 수집기

m.place.naver.com/{place_id}/home 페이지에서 업체 정보를 수집한다.

수집 항목 (place_manager.py 참고, 지도/주변정보 제외):
  - 상호명, 카테고리
  - 주소, 전화번호, 홈페이지
  - 영업시간 (요일별), 브레이크타임, 라스트오더
  - 방문자 리뷰 수, 평점, 블로그 리뷰 수
  - 저장(북마크) 수
  - 메뉴 목록 (이름 + 가격)
  - 사진 수

제외:
  - 지도/위치 정보 (extract_map_markers)
  - 주변 정보 (around_only 모드)
  - 구글 드라이브 업로드
──────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from playwright.async_api import async_playwright

from workers.crawler.stealth import (
    build_stealth_context,
    new_stealth_page,
    safe_goto,
    human_delay,
    human_scroll,
)
from workers.crawler.parsers import PlaceInfoParser
from app.utils.naver import build_mobile_place_url

logger = logging.getLogger(__name__)


# ── 예외 ──────────────────────────────────────────────────────────────────────

class PlaceInfoError(Exception):
    """플레이스 정보 수집 실패"""


class PlaceNotFoundError(PlaceInfoError):
    """존재하지 않는 플레이스 ID"""


# ── 플레이스 정보 수집기 ───────────────────────────────────────────────────────

async def fetch_place_info(
    place_id: str,
    proxy: Optional[dict] = None,
    timeout_ms: int = 30_000,
) -> dict:
    """
    네이버 플레이스 기본 정보를 수집해 dict로 반환한다.

    Args:
        place_id: 네이버 플레이스 MID (숫자 문자열)
        proxy: {"server": "http://ip:port"} 프록시 설정 (선택)
        timeout_ms: 페이지 로드 타임아웃 (ms)

    Returns:
        {
          "place_id": str,
          "name": str,
          "category": str,
          "address": str,
          "phone": str,
          "homepage": str,
          "hours": list[dict],      # [{day, day_ko, open, close, is_holiday}]
          "break_time": str,
          "last_order": str,
          "review_count": int,
          "avg_rating": float,
          "blog_review_count": int,
          "saved_count": int,
          "visitor_monthly": int,
          "menus": list[dict],      # [{name, price, is_recommended}]
          "photo_count": int,
          "ad_power_link": bool,
          "ad_place_ad": bool,
          "crawl_success": bool,
          "error": str | None,
        }

    Raises:
        PlaceNotFoundError: 404 또는 빈 페이지
        PlaceInfoError: 기타 수집 실패
    """
    url = build_mobile_place_url(place_id)
    logger.info("플레이스 정보 수집 시작: place_id=%s url=%s", place_id, url)

    pw = None
    browser = None
    try:
        pw = await async_playwright().start()
        browser, context = await build_stealth_context(pw, proxy=proxy)
        page = await new_stealth_page(context)

        # ── 페이지 이동 ────────────────────────────────────────────────────
        response = await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")

        if response is None or response.status == 404:
            raise PlaceNotFoundError(f"플레이스를 찾을 수 없습니다: {place_id}")

        if response.status >= 400:
            raise PlaceInfoError(f"HTTP {response.status}: {url}")

        # ── 콘텐츠 로드 대기 ──────────────────────────────────────────────
        # 업체명이 나타날 때까지 최대 10초 대기
        try:
            await page.wait_for_selector(
                "h1.GHAhO, h1.place_name, span.GHAhO, h1",
                timeout=10_000,
            )
        except Exception:
            logger.warning("업체명 셀렉터 타임아웃 — 계속 진행")

        # 자연스러운 스크롤 (DOM 전체 렌더링 유도)
        await human_delay(500, 1000)
        await human_scroll(page, steps=3)
        await human_delay(300, 700)

        # ── 파싱 ──────────────────────────────────────────────────────────
        parser = PlaceInfoParser()
        info = await parser.parse(page)

        if not info.get("name"):
            raise PlaceNotFoundError(
                f"업체명을 파싱할 수 없습니다 (place_id={place_id}). "
                "삭제된 업체이거나 URL이 잘못되었을 수 있습니다."
            )

        return {
            "place_id": place_id,
            **info,
            "crawl_success": True,
            "error": None,
        }

    except (PlaceNotFoundError, PlaceInfoError):
        raise
    except Exception as e:
        logger.error("플레이스 정보 수집 오류 [%s]: %s", place_id, e)
        raise PlaceInfoError(str(e)) from e
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
        if pw:
            try:
                await pw.stop()
            except Exception:
                pass


# ── Place 모델 DB 반영 헬퍼 ───────────────────────────────────────────────────

def apply_place_info_to_model(place_model, info: dict) -> None:
    """
    fetch_place_info() 결과를 SQLAlchemy Place 모델에 반영한다.

    Args:
        place_model: app.models.place.Place 인스턴스
        info: fetch_place_info() 반환값
    """
    # 기본 필드
    if info.get("name"):
        place_model.name = info["name"]
    if info.get("category"):
        place_model.category = info["category"]
    if info.get("address"):
        place_model.address = info["address"]

    # extra_data JSONB에 나머지 저장
    extra = place_model.extra_data or {}
    extra.update({
        "phone":              info.get("phone", ""),
        "homepage":           info.get("homepage", ""),
        "hours":              info.get("hours", []),
        "break_time":         info.get("break_time", ""),
        "last_order":         info.get("last_order", ""),
        "review_count":       info.get("review_count", 0),
        "avg_rating":         info.get("avg_rating", 0.0),
        "blog_review_count":  info.get("blog_review_count", 0),
        "saved_count":        info.get("saved_count", 0),
        "visitor_monthly":    info.get("visitor_monthly", 0),
        "menus":              info.get("menus", []),
        "photo_count":        info.get("photo_count", 0),
        "ad_power_link":      info.get("ad_power_link", False),
        "ad_place_ad":        info.get("ad_place_ad", False),
        "crawl_errors":       info.get("raw_errors", []),
    })
    place_model.extra_data = extra
