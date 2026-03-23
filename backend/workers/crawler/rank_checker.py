"""
workers/crawler/rank_checker.py
──────────────────────────────────────────────────────────────────────────────
키워드 순위 체크 오케스트레이터

하나의 (키워드, MID) 쌍에 대해:
  1. 스텔스 브라우저 생성
  2. m.search.naver.com 검색 페이지 접근
  3. PlaceSectionParser로 순위 탐색
  4. 결과 반환 (또는 재시도)

세션 재사용:
  - 키워드를 여러 개 연속 체크할 때 브라우저를 재사용한다.
  - 20회마다 또는 세션 오류 시 브라우저를 재시작한다.
  - 이 방식으로 실제 프로그램의 "20개마다 초기화" 전략을 재현한다.

IP 차단 감지:
  - 페이지 타이틀에 "로봇" / "captcha" 포함 시 차단으로 판단
  - 연속 3회 차단 시 BotDetectedError 발생
──────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Optional
from urllib.parse import quote

from playwright.async_api import async_playwright, BrowserContext, Page

from workers.crawler.stealth import (
    build_stealth_context,
    human_delay,
    human_scroll,
    human_mouse_move,
    new_stealth_page,
    safe_goto,
)
from workers.crawler.parsers import PlaceSectionParser

logger = logging.getLogger(__name__)


# ── 예외 ──────────────────────────────────────────────────────────────────────

class BotDetectedError(Exception):
    """네이버 봇 탐지 차단 발생"""


class BrowserSessionError(Exception):
    """브라우저 세션 오류"""


# ── 검색 URL 빌더 ──────────────────────────────────────────────────────────────

def build_search_url(keyword: str) -> str:
    """
    모바일 네이버 검색 URL 생성.
    실제 프로그램과 동일하게 m.search.naver.com 사용.
    """
    encoded = quote(keyword)
    return f"https://m.search.naver.com/search.naver?query={encoded}"


# ── 봇 탐지 감지 ───────────────────────────────────────────────────────────────

async def is_bot_blocked(page: Page) -> bool:
    """
    현재 페이지가 봇 차단 상태인지 확인.
    - 타이틀에 captcha/로봇 포함
    - 비정상적으로 짧은 페이지 (본문 텍스트 < 100자)
    """
    try:
        title = await page.title()
        title_lower = title.lower()
        if any(kw in title_lower for kw in ["captcha", "robot", "로봇", "차단", "blocked"]):
            return True

        # 본문 길이 체크
        body_text = await page.inner_text("body")
        if len(body_text.strip()) < 100:
            return True
    except Exception:
        pass
    return False


# ── 세션 관리 ─────────────────────────────────────────────────────────────────

class RankCheckerSession:
    """
    단일 Playwright 브라우저 세션 래퍼.

    - 브라우저/컨텍스트를 내부에서 관리
    - check_count 를 추적해 RESET_EVERY 마다 자동 재시작
    - 봇 탐지 시 즉시 재시작 + consecutive_blocks 카운트
    """

    RESET_EVERY = 20        # N회마다 브라우저 재시작 (실제 프로그램 전략)
    MAX_BLOCKS = 3          # 연속 봇 차단 허용 횟수
    SEARCH_WAIT_AFTER = 0.5 # 검색 후 추가 대기 (초)

    def __init__(self, proxy: Optional[dict] = None):
        self.proxy = proxy
        self._pw = None
        self._browser = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self.check_count = 0
        self.consecutive_blocks = 0
        self._parser = PlaceSectionParser()

    async def start(self) -> None:
        """브라우저 시작."""
        self._pw = await async_playwright().start()
        self._browser, self._context = await build_stealth_context(
            self._pw, proxy=self.proxy
        )
        self._page = await new_stealth_page(self._context)
        logger.info("RankCheckerSession: 브라우저 시작 완료")

    async def restart(self) -> None:
        """브라우저 재시작 (세션 초기화)."""
        logger.info("RankCheckerSession: 세션 재시작 중...")
        await self.stop()
        await asyncio.sleep(random.uniform(2, 4))
        await self.start()
        self.check_count = 0
        logger.info("RankCheckerSession: 세션 재시작 완료")

    async def stop(self) -> None:
        """브라우저 종료."""
        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass
        try:
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None

    async def check_keyword(
        self,
        keyword: str,
        target_mid: str,
        max_rank: int = 5,
    ) -> dict:
        """
        단일 키워드에 대한 순위 체크.

        Args:
            keyword: 검색할 키워드 (예: "강남 치킨집")
            target_mid: 찾을 업체의 네이버 플레이스 MID
            max_rank: 최대 순위 탐색 범위

        Returns:
            PlaceSectionParser.find_rank() 결과 dict +
            {
              "keyword": str,
              "target_mid": str,
              "bot_blocked": bool,
              "session_restarted": bool,
            }
        """
        if not self._page:
            raise BrowserSessionError("브라우저가 시작되지 않았습니다")

        # ── RESET_EVERY 마다 세션 초기화 ────────────────────────────────────
        if self.check_count > 0 and self.check_count % self.RESET_EVERY == 0:
            logger.info(
                "RankCheckerSession: %d회 검색 완료 → 세션 초기화", self.check_count
            )
            await self.restart()

        session_restarted = False
        bot_blocked = False

        try:
            # ── 검색 페이지 이동 ────────────────────────────────────────────
            search_url = build_search_url(keyword)
            ok = await safe_goto(self._page, search_url, wait_until="domcontentloaded")

            if not ok:
                # 페이지 이동 실패 → 세션 재시작 후 1회 재시도
                await self.restart()
                session_restarted = True
                ok = await safe_goto(self._page, search_url, wait_until="domcontentloaded")
                if not ok:
                    return self._error_result(keyword, target_mid, "페이지 이동 실패")

            # 인간형 딜레이
            await human_delay(600, 1500)

            # ── 봇 탐지 확인 ──────────────────────────────────────────────
            if await is_bot_blocked(self._page):
                self.consecutive_blocks += 1
                bot_blocked = True
                logger.warning(
                    "봇 탐지 차단 (연속 %d회): %s", self.consecutive_blocks, keyword
                )

                if self.consecutive_blocks >= self.MAX_BLOCKS:
                    raise BotDetectedError(
                        f"연속 {self.consecutive_blocks}회 봇 탐지 차단"
                    )

                # 차단 시 더 긴 대기 후 재시작
                await asyncio.sleep(random.uniform(30, 60))
                await self.restart()
                session_restarted = True

                # 재시도
                ok = await safe_goto(self._page, search_url, wait_until="domcontentloaded")
                if not ok or await is_bot_blocked(self._page):
                    return self._error_result(
                        keyword, target_mid, "봇 차단 이후 재시도 실패"
                    )

            # 성공 시 consecutive_blocks 초기화
            self.consecutive_blocks = 0

            # ── 자연스러운 스크롤/마우스 ───────────────────────────────────
            await human_mouse_move(self._page)
            await asyncio.sleep(self.SEARCH_WAIT_AFTER)

            # ── 순위 체크 ─────────────────────────────────────────────────
            rank_result = await self._parser.find_rank(
                self._page, target_mid, max_rank=max_rank
            )

            self.check_count += 1

            return {
                **rank_result,
                "keyword": keyword,
                "target_mid": target_mid,
                "bot_blocked": bot_blocked,
                "session_restarted": session_restarted,
            }

        except BotDetectedError:
            raise
        except Exception as e:
            logger.error("키워드 체크 오류 [%s]: %s", keyword, e)
            return self._error_result(
                keyword, target_mid, f"오류: {e}",
                bot_blocked=bot_blocked,
                session_restarted=session_restarted,
            )

    @staticmethod
    def _error_result(
        keyword: str,
        target_mid: str,
        status: str,
        bot_blocked: bool = False,
        session_restarted: bool = False,
    ) -> dict:
        return {
            "rank": None,
            "company_name": "",
            "section_exists": False,
            "is_top_section": False,
            "cpc_count": 0,
            "total_places": 0,
            "status": status,
            "keyword": keyword,
            "target_mid": target_mid,
            "bot_blocked": bot_blocked,
            "session_restarted": session_restarted,
        }


# ── 고수준 API: 단일 키워드 one-shot 체크 ────────────────────────────────────

async def check_single_keyword(
    keyword: str,
    target_mid: str,
    max_rank: int = 5,
    proxy: Optional[dict] = None,
) -> dict:
    """
    새 세션을 열어 단일 키워드를 체크하고 닫는다.
    Celery 태스크에서 단독으로 호출할 때 사용.
    """
    session = RankCheckerSession(proxy=proxy)
    try:
        await session.start()
        result = await session.check_keyword(keyword, target_mid, max_rank=max_rank)
        return result
    finally:
        await session.stop()


# ── 고수준 API: 배치 체크 (세션 재사용) ──────────────────────────────────────

async def check_keywords_batch(
    tasks: list[dict],
    proxy: Optional[dict] = None,
    delay_between: tuple[int, int] = (800, 2500),
) -> list[dict]:
    """
    여러 (keyword, mid) 쌍을 하나의 세션으로 연속 체크한다.

    Args:
        tasks: [{"keyword": str, "mid": str, "max_rank": int}, ...]
        proxy: 프록시 설정
        delay_between: 검색 사이 대기 (ms 최소, ms 최대)

    Returns:
        각 task에 대한 rank_result list
    """
    session = RankCheckerSession(proxy=proxy)
    results = []

    try:
        await session.start()

        for i, task in enumerate(tasks):
            keyword = task["keyword"]
            mid = task["mid"]
            max_rank = task.get("max_rank", 5)

            try:
                result = await session.check_keyword(keyword, mid, max_rank=max_rank)
                results.append(result)
                logger.info(
                    "[%d/%d] %s → 순위: %s (%s)",
                    i + 1, len(tasks),
                    keyword,
                    result.get("rank", "미발견"),
                    result.get("status", ""),
                )
            except BotDetectedError as e:
                logger.error("봇 탐지로 배치 중단: %s", e)
                # 나머지 태스크는 error 상태로 채움
                for remaining in tasks[i:]:
                    results.append(
                        RankCheckerSession._error_result(
                            remaining["keyword"],
                            remaining["mid"],
                            "봇 탐지로 중단",
                            bot_blocked=True,
                        )
                    )
                break

            # 검색 사이 인간형 딜레이
            min_ms, max_ms = delay_between
            await human_delay(min_ms, max_ms)

    finally:
        await session.stop()

    return results
