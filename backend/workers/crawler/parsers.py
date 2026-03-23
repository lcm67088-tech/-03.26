"""
workers/crawler/parsers.py
──────────────────────────────────────────────────────────────────────────────
네이버 모바일 검색 결과 DOM 파서

실제 코드(integrated_keyword_manager.py) 기반으로 구현.
네이버 UI는 수시로 바뀌므로 셀렉터를 우선순위별로 다단계로 시도한다.

수집 대상:
  [순위 체크]
  - 플레이스 섹션 존재 여부 + 최상단 위치 여부
  - CPC 광고 배지 수
  - 업체별 MID 추출 (data-loc_plc-doc-id 또는 href)
  - 업체명 추출

  [플레이스 정보 — m.place.naver.com/{id}/home]
  - 상호명, 카테고리, 주소, 전화번호
  - 영업시간 (요일별), 브레이크타임, 라스트오더
  - 리뷰 수, 평점, 블로그 리뷰 수
  - 저장(북마크) 수
  - 메뉴/가격 목록
  - 사진 수
──────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import re
import asyncio
import logging
from typing import Optional

from playwright.async_api import Page, ElementHandle

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. 순위 체크 파서
# ═══════════════════════════════════════════════════════════════════════════════

class PlaceSectionParser:
    """
    m.search.naver.com 검색 결과에서 플레이스 섹션을 파싱한다.

    네이버 DOM은 자주 바뀌므로 셀렉터를 3~4단계로 fallback한다.
    실제 integrated_keyword_manager.py의 로직을 Playwright async로 이식.
    """

    # ── 플레이스 섹션 셀렉터 (우선순위 순) ─────────────────────────────────────
    SECTION_SELECTORS = [
        # 방법 1: data-laim-exp-id 속성 (가장 명확)
        "div[data-laim-exp-id='loc_plc']",
        "div.place_section[data-laim-exp-id='loc_plc']",
        # 방법 2: place_section 클래스
        "div.place_section",
        # 방법 3: 플레이스 아이템의 공통 부모 (신규 구조)
        "div:has(li[data-loc_plc-doc-id])",
        "div:has(li.VLTHu)",
    ]

    # ── 플레이스 아이템 셀렉터 (각 업체 row) ───────────────────────────────────
    ITEM_SELECTORS = [
        # 신규 구조 (2024~)
        "li[data-loc_plc-doc-id]",
        "li.VLTHu[data-loc_plc-doc-id]",
        # 구조 A: UEzoS
        "li.UEzoS.rIj4c",
        "li.UEzoS",
        # 구조 B: CHC5F
        "div.CHC5F",
        # 구조 C: VLTHu (data 속성 없이)
        "li.VLTHu",
    ]

    # ── CPC 광고 배지 셀렉터 ──────────────────────────────────────────────────
    CPC_SELECTORS = [
        "a.gU6bV",                          # 기존
        "li[class*='cZnHG']",               # 신규
        "div[class*='cZnHG']",
    ]

    # ── 업체명 셀렉터 ─────────────────────────────────────────────────────────
    NAME_SELECTORS = [
        "span.YwYLL",                        # 신규 2024~
        "a.place_bluelink .YwYLL",
        "a.place_bluelink",                  # 기존
        "span.TYaxT",
        "span.place_name",
        "a.place_name",
    ]

    # ── URL에서 MID 추출 패턴 ─────────────────────────────────────────────────
    MID_URL_PATTERN = re.compile(
        r'/(?:place|restaurant|hospital|hairshop|attraction|nailshop|'
        r'waxing|pension|parking|law|academy|animalhospital|'
        r'curtain|moving|cleaning|health|pilates|shaped|etc)/(\d+)',
        re.IGNORECASE,
    )

    async def find_section(self, page: Page) -> Optional[ElementHandle]:
        """플레이스 섹션 ElementHandle 반환. 없으면 None."""
        for selector in self.SECTION_SELECTORS:
            try:
                el = await page.query_selector(selector)
                if el and await el.is_visible():
                    # place_section 클래스인 경우 제목에 "플레이스" 포함 여부 확인
                    if "place_section" in selector and "data-laim" not in selector:
                        try:
                            title_el = await el.query_selector(
                                ".place_section_header_title, h3.place_section_header div"
                            )
                            if title_el:
                                title_text = await title_el.inner_text()
                                if "플레이스" not in title_text:
                                    continue
                        except Exception:
                            pass
                    return el
            except Exception:
                continue
        return None

    async def is_top_section(self, page: Page, section: ElementHandle) -> bool:
        """
        플레이스 섹션이 검색결과 최상단에 위치하는지 판단.
        검색 입력창과 섹션 사이의 거리가 250px 미만이면 최상단.
        """
        try:
            search_input = await page.query_selector(
                "input.search_input, input[type='search']"
            )
            base_y = 0
            if search_input:
                box = await search_input.bounding_box()
                base_y = box["y"] if box else 0

            section_box = await section.bounding_box()
            if section_box:
                distance = section_box["y"] - base_y
                return distance < 250
        except Exception:
            pass
        return False

    async def count_cpc_ads(self, page: Page, section: Optional[ElementHandle]) -> int:
        """CPC 광고 배지 수 반환."""
        count = 0
        for selector in self.CPC_SELECTORS:
            try:
                ctx = section if section else page
                badges = await ctx.query_selector_all(selector)
                for badge in badges:
                    if await badge.is_visible():
                        count += 1
                if count:
                    return count
            except Exception:
                continue
        return 0

    async def extract_mid_from_element(self, el: ElementHandle) -> Optional[str]:
        """
        플레이스 아이템 엘리먼트에서 MID(업체 ID) 추출.

        우선순위:
          1) data-loc_plc-doc-id 속성 (신규, 가장 확실)
          2) 내부 <a> href URL 파싱
        """
        # 방법 1: data 속성
        try:
            doc_id = await el.get_attribute("data-loc_plc-doc-id")
            if doc_id and doc_id.strip().isdigit():
                return doc_id.strip()
        except Exception:
            pass

        # 방법 2: href에서 파싱
        try:
            links = await el.query_selector_all("a[href]")
            for link in links:
                href = await link.get_attribute("href") or ""
                if "/place/" in href or "/restaurant/" in href:
                    m = self.MID_URL_PATTERN.search(href)
                    if m:
                        return m.group(1)
        except Exception:
            pass

        return None

    async def extract_name_from_element(self, el: ElementHandle) -> str:
        """업체명 추출."""
        for selector in self.NAME_SELECTORS:
            try:
                name_el = await el.query_selector(selector)
                if name_el:
                    text = (await name_el.inner_text()).strip()
                    if text:
                        return text
            except Exception:
                continue

        # fallback: 첫 번째 텍스트 라인
        try:
            full_text = (await el.inner_text()).strip()
            first_line = full_text.split("\n")[0].strip()
            if first_line:
                return first_line
        except Exception:
            pass
        return ""

    async def find_rank(
        self,
        page: Page,
        target_mid: str,
        max_rank: int = 5,
    ) -> dict:
        """
        검색 결과 플레이스 섹션에서 target_mid의 순위를 찾는다.

        Args:
            page: 이미 검색 결과 페이지가 로드된 Playwright Page
            target_mid: 찾을 업체의 네이버 플레이스 MID
            max_rank: 최대 탐색 순위 (기본 5위, 전체 체크 시 100)

        Returns:
            {
              "rank": int | None,          # 순위 (미발견 시 None)
              "company_name": str,         # 업체명
              "section_exists": bool,      # 플레이스 섹션 존재 여부
              "is_top_section": bool,      # 최상단 위치 여부
              "cpc_count": int,            # CPC 광고 수
              "total_places": int,         # 섹션 내 전체 업체 수
              "status": str,               # 상세 상태 메시지
            }
        """
        result = {
            "rank": None,
            "company_name": "",
            "section_exists": False,
            "is_top_section": False,
            "cpc_count": 0,
            "total_places": 0,
            "status": "플레이스 섹션 없음",
        }

        # 페이지 최상단 스크롤
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(0.3)

        # 1. 플레이스 섹션 탐색
        section = await self.find_section(page)
        if not section:
            result["status"] = "플레이스 섹션 없음"
            return result

        result["section_exists"] = True
        result["is_top_section"] = await self.is_top_section(page, section)
        result["cpc_count"] = await self.count_cpc_ads(page, section)

        # 2. 아이템 순회하며 MID 매칭
        seen_mids: set[str] = set()
        all_items: list[ElementHandle] = []

        scroll_count = 0
        max_scrolls = 3 if max_rank <= 5 else 20
        last_height = await page.evaluate("document.body.scrollHeight")

        while scroll_count <= max_scrolls:
            # 아이템 셀렉터 순서대로 시도
            items: list[ElementHandle] = []
            for selector in self.ITEM_SELECTORS:
                try:
                    ctx = section if section else page
                    items = await ctx.query_selector_all(selector)
                    if items:
                        break
                except Exception:
                    continue

            if not items and scroll_count == 0:
                result["status"] = "검색 결과 없음"
                return result

            new_found = 0
            for item in items[:100]:
                if item in all_items:
                    continue

                mid = await self.extract_mid_from_element(item)
                if not mid or mid in seen_mids:
                    continue

                seen_mids.add(mid)
                all_items.append(item)
                new_found += 1

                if mid == target_mid:
                    rank = len(all_items)
                    name = await self.extract_name_from_element(item)
                    result["rank"] = rank
                    result["company_name"] = name
                    result["total_places"] = len(items)
                    result["status"] = f"{rank}위 발견"
                    return result

                # 5위 체크 모드는 5개 이상이면 종료
                if max_rank <= 5 and len(all_items) >= max_rank:
                    result["total_places"] = len(items)
                    result["status"] = f"{max_rank}위까지 확인, 미발견"
                    return result

            result["total_places"] = len(all_items)

            if max_rank <= 5:
                break

            if new_found == 0:
                break

            if len(all_items) >= max_rank:
                break

            # 더보기/펼쳐보기 버튼 처리
            await self._click_more_button(page, section)

            # 스크롤 다운
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.2)

            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
            scroll_count += 1

        checked = len(all_items)
        result["status"] = f"{checked}위까지 확인, 미발견"
        return result

    async def _click_more_button(
        self, page: Page, section: Optional[ElementHandle]
    ) -> bool:
        """더보기/펼쳐보기 버튼 클릭. 클릭 성공 시 True."""
        ctx = section if section else page
        button_texts = ["펼쳐서 더보기", "펼쳐보기", "더보기"]
        for text in button_texts:
            try:
                btn = await ctx.query_selector(
                    f"button:has-text('{text}'), a:has-text('{text}'), "
                    f"span[role='button']:has-text('{text}')"
                )
                if btn and await btn.is_visible():
                    await btn.scroll_into_view_if_needed()
                    await asyncio.sleep(0.3)
                    await btn.click()
                    await asyncio.sleep(0.8)
                    return True
            except Exception:
                continue
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# 2. 플레이스 기본 정보 파서
# ═══════════════════════════════════════════════════════════════════════════════

class PlaceInfoParser:
    """
    m.place.naver.com/{place_id}/home 페이지에서 업체 정보를 파싱한다.

    수집 항목:
      - 상호명, 카테고리
      - 주소, 전화번호, 홈페이지
      - 영업시간 (요일별), 브레이크타임, 라스트오더
      - 리뷰 수, 평점 (방문자 리뷰 + 블로그 리뷰)
      - 저장(북마크) 수
      - 메뉴 목록 (이름 + 가격)
      - 대표 사진 수 (카테고리별)
    """

    async def parse(self, page: Page) -> dict:
        """
        현재 page에서 플레이스 정보 전부를 파싱해 dict로 반환.

        Returns:
            {
              "name": str,
              "category": str,
              "address": str,
              "phone": str,
              "homepage": str,
              "hours": list[dict],     # [{day, open, close, is_holiday}]
              "break_time": str,
              "last_order": str,
              "review_count": int,
              "avg_rating": float,
              "blog_review_count": int,
              "saved_count": int,
              "menus": list[dict],     # [{name, price, is_recommended}]
              "photo_count": int,
              "raw_errors": list[str], # 파싱 실패한 항목
            }
        """
        result: dict = {
            "name": "",
            "category": "",
            "address": "",
            "phone": "",
            "homepage": "",
            "hours": [],
            "break_time": "",
            "last_order": "",
            "review_count": 0,
            "avg_rating": 0.0,
            "blog_review_count": 0,
            "saved_count": 0,
            "visitor_monthly": 0,
            "menus": [],
            "photo_count": 0,
            "ad_power_link": False,
            "ad_place_ad": False,
            "raw_errors": [],
        }

        tasks = [
            ("name/category", self._parse_name_category(page, result)),
            ("address/phone",  self._parse_contact(page, result)),
            ("hours",          self._parse_hours(page, result)),
            ("reviews",        self._parse_reviews(page, result)),
            ("visitor",        self._parse_visitor_monthly(page, result)),
            ("menus",          self._parse_menus(page, result)),
            ("photos",         self._parse_photos(page, result)),
            ("ads",            self._parse_ads(page, result)),
        ]

        for label, coro in tasks:
            try:
                await coro
            except Exception as e:
                logger.warning("파싱 실패 [%s]: %s", label, e)
                result["raw_errors"].append(f"{label}: {e}")

        return result

    # ── 상호명 / 카테고리 ────────────────────────────────────────────────────

    async def _parse_name_category(self, page: Page, result: dict) -> None:
        # 상호명
        for sel in ["h1.GHAhO", "span.GHAhO", "h1.place_name", "h1"]:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                if text:
                    result["name"] = text
                    break

        # 카테고리
        for sel in ["span.lnJFt", "span.category", "a.category", "span.DJOBl"]:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                if text:
                    result["category"] = text
                    break

    # ── 주소 / 전화번호 / 홈페이지 ──────────────────────────────────────────

    async def _parse_contact(self, page: Page, result: dict) -> None:
        # 주소 — span.LDgIH 또는 address 태그
        for sel in ["span.LDgIH", "p.LDgIH", "address", "span.road_address"]:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                # "지번" 제거
                text = re.sub(r'\s*지번.*', '', text).strip()
                if text:
                    result["address"] = text
                    break

        # 전화번호 — a[href^="tel:"]
        tel_el = await page.query_selector("a[href^='tel:']")
        if tel_el:
            href = await tel_el.get_attribute("href") or ""
            phone = href.replace("tel:", "").strip()
            if phone:
                result["phone"] = phone
        else:
            # fallback: span.xlx3B, span.phone
            for sel in ["span.xlx3B", "span.phone", "span.N8wgR"]:
                el = await page.query_selector(sel)
                if el:
                    text = (await el.inner_text()).strip()
                    if re.search(r'\d{2,4}-\d{3,4}-\d{4}', text):
                        result["phone"] = text
                        break

        # 홈페이지 — a[href*="://"] 에서 naver 도메인 제외
        links = await page.query_selector_all("a[href]")
        for link in links:
            href = await link.get_attribute("href") or ""
            if (
                href.startswith("http")
                and "naver.com" not in href
                and "kakao" not in href
                and len(href) < 200
            ):
                result["homepage"] = href
                break

    # ── 영업시간 ─────────────────────────────────────────────────────────────

    async def _parse_hours(self, page: Page, result: dict) -> None:
        """
        영업시간 파싱.
        네이버 플레이스 영업시간은 보통 숨겨진 레이어에 있어
        "영업시간" 버튼을 클릭해서 펼쳐야 한다.
        """
        DAY_MAP = {"월": "MON", "화": "TUE", "수": "WED", "목": "THU",
                   "금": "FRI", "토": "SAT", "일": "SUN"}

        # 영업시간 토글 버튼 클릭 시도
        for toggle_sel in [
            "a.tMImt",          # 기존 펼치기
            "button.A_cdD",     # 신규
            "span[role='button']:has-text('영업시간')",
            "a:has-text('영업시간')",
        ]:
            try:
                btn = await page.query_selector(toggle_sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    await asyncio.sleep(0.5)
                    break
            except Exception:
                continue

        # 영업시간 컨테이너 찾기
        hours_container = None
        for sel in ["div.w9YEd", "div.O8qbU", "div.time_detail", "ul.time_list"]:
            hours_container = await page.query_selector(sel)
            if hours_container:
                break

        if not hours_container:
            return

        # 요일별 파싱
        hour_rows = await hours_container.query_selector_all(
            "li, tr, div[class*='day']"
        )
        for row in hour_rows:
            try:
                text = (await row.inner_text()).strip()
                # "월 11:00 ~ 22:00" 형태 파싱
                m = re.search(
                    r'([월화수목금토일])\s*'
                    r'(\d{1,2}:\d{2})\s*[~～\-]\s*(\d{1,2}:\d{2})',
                    text
                )
                if m:
                    day_ko = m.group(1)
                    result["hours"].append({
                        "day": DAY_MAP.get(day_ko, day_ko),
                        "day_ko": day_ko,
                        "open": m.group(2),
                        "close": m.group(3),
                        "is_holiday": False,
                    })
                    continue

                # 휴무일 처리
                day_m = re.search(r'([월화수목금토일])', text)
                if day_m and ("휴무" in text or "정기" in text or "closed" in text.lower()):
                    day_ko = day_m.group(1)
                    result["hours"].append({
                        "day": DAY_MAP.get(day_ko, day_ko),
                        "day_ko": day_ko,
                        "open": None,
                        "close": None,
                        "is_holiday": True,
                    })
            except Exception:
                continue

        # 브레이크타임
        for sel in ["span.uFpDK", "span.break_time", "li:has-text('브레이크')"]:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                bt_m = re.search(
                    r'(\d{1,2}:\d{2})\s*[~～\-]\s*(\d{1,2}:\d{2})', text
                )
                if bt_m:
                    result["break_time"] = f"{bt_m.group(1)} ~ {bt_m.group(2)}"
                    break

        # 라스트오더
        for sel in ["span.last_order", "li:has-text('라스트 오더')", "li:has-text('last order')"]:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                lo_m = re.search(r'(\d{1,2}:\d{2})', text)
                if lo_m:
                    result["last_order"] = lo_m.group(1)
                    break

    # ── 리뷰 수 / 평점 ───────────────────────────────────────────────────────

    async def _parse_reviews(self, page: Page, result: dict) -> None:
        """
        방문자 리뷰, 블로그 리뷰, 평점, 저장 수 파싱.
        네이버 UI가 자주 변경되므로 다단계 fallback 적용.
        """
        # ── 평점 ─────────────────────────────────────────────────────────────
        for sel in [
            "span.PXMot.LXIwF",   # 2024 신규
            "em.LXIwF",
            "span.h69bs em",
            "span.score em",
            "div.dAsGb em",       # 2025 추가 후보
            "span[class*='rating'] em",
        ]:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                try:
                    v = float(text)
                    if 0.0 < v <= 5.0:
                        result["avg_rating"] = v
                        break
                except ValueError:
                    pass

        # ── 방문자 리뷰 수 ───────────────────────────────────────────────────
        for sel in [
            "a[href*='review/visitor'] em",
            "a[href*='review/visitor'] span",
            "span.PXMot em",
            "a:has-text('방문자 리뷰') em",
            "a:has-text('방문자리뷰') em",
            "em.place_review_count",
            "div.k66bV a:first-child em",   # 2025 후보
        ]:
            el = await page.query_selector(sel)
            if el:
                text = re.sub(r'[^\d]', '', (await el.inner_text()).strip())
                if text.isdigit() and int(text) > 0:
                    result["review_count"] = int(text)
                    break

        # ── 블로그 리뷰 수 ───────────────────────────────────────────────────
        for sel in [
            "a[href*='review/ugc'] em",
            "a[href*='review/ugc'] span",
            "a:has-text('블로그 리뷰') em",
            "a:has-text('블로그리뷰') em",
            "a:has-text('블로그') em",
            "div.k66bV a:last-child em",    # 2025 후보
        ]:
            el = await page.query_selector(sel)
            if el:
                text = re.sub(r'[^\d]', '', (await el.inner_text()).strip())
                if text.isdigit():
                    result["blog_review_count"] = int(text)
                    break

        # ── 저장 수 ──────────────────────────────────────────────────────────
        for sel in [
            "span.place_save em",
            "a:has-text('저장') em",
            "button:has-text('저장') em",
            "span.GYFGb em",
            "div[class*='save'] em",
            "span.lPzHi ~ em",             # 2025 후보
        ]:
            el = await page.query_selector(sel)
            if el:
                raw = re.sub(r'[^\d]', '', (await el.inner_text()).strip())
                if raw.isdigit():
                    result["saved_count"] = int(raw)
                    break

        # ── 전체 텍스트 fallback ──────────────────────────────────────────────
        if result["review_count"] == 0 or result["blog_review_count"] == 0:
            try:
                full_text = await page.inner_text("body")
                if result["review_count"] == 0:
                    m = re.search(r'방문자\s*리뷰\D{0,5}([\d,]+)', full_text)
                    if m:
                        result["review_count"] = int(m.group(1).replace(",", ""))
                if result["blog_review_count"] == 0:
                    m2 = re.search(r'블로그\s*리뷰\D{0,5}([\d,]+)', full_text)
                    if m2:
                        result["blog_review_count"] = int(m2.group(1).replace(",", ""))
                if result["saved_count"] == 0:
                    m3 = re.search(r'저장\D{0,5}([\d,]+)', full_text)
                    if m3:
                        v = int(m3.group(1).replace(",", ""))
                        if v < 1_000_000:  # 비상식적으로 큰 수 제외
                            result["saved_count"] = v
            except Exception:
                pass

    # ── 월 방문자 수 ─────────────────────────────────────────────────────────

    async def _parse_visitor_monthly(self, page: Page, result: dict) -> None:
        """
        월 방문자 수 파싱.
        네이버 플레이스 홈의 '이달의 방문자' 또는 인사이트 섹션.
        """
        # 방법 1: 인사이트/방문자 영역 직접 탐색
        for sel in [
            "div.CLbD1 strong",
            "strong.visitor_count",
            "span[class*='visitor'] strong",
            "div[class*='insight'] strong",
            "p:has-text('방문자') strong",
            "div:has-text('이달') strong",
        ]:
            el = await page.query_selector(sel)
            if el:
                raw = re.sub(r'[^\d]', '', (await el.inner_text()).strip())
                if raw.isdigit() and int(raw) > 0:
                    result["visitor_monthly"] = int(raw)
                    return

        # 방법 2: 전체 텍스트에서 패턴 파싱
        try:
            full_text = await page.inner_text("body")
            patterns = [
                r'이달의\s*방문자\D{0,10}([\d,]+)',
                r'월\s*방문자\D{0,10}([\d,]+)',
                r'방문자\s*수\D{0,10}([\d,]+)',
            ]
            for pat in patterns:
                m = re.search(pat, full_text)
                if m:
                    v = int(m.group(1).replace(",", ""))
                    if 0 < v < 10_000_000:
                        result["visitor_monthly"] = v
                        return
        except Exception:
            pass

    # ── 광고 노출 여부 ────────────────────────────────────────────────────────

    async def _parse_ads(self, page: Page, result: dict) -> None:
        """
        파워링크 / 플레이스 광고 노출 여부 파싱.
        플레이스 홈 페이지에서 광고 배지 확인.
        """
        try:
            full_text = await page.inner_text("body")
            # 파워링크 광고
            if re.search(r'파워링크|PowerLink', full_text, re.IGNORECASE):
                result["ad_power_link"] = True
            # 플레이스 광고 배지
            for sel in [
                "span:has-text('광고')",
                "em:has-text('AD')",
                "span.ad_badge",
                "span.gU6bV",
            ]:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    result["ad_place_ad"] = True
                    break
        except Exception:
            pass

    # ── 메뉴 ─────────────────────────────────────────────────────────────────

    async def _parse_menus(self, page: Page, result: dict) -> None:
        """
        메뉴/가격 목록 파싱.
        메뉴 탭으로 이동할 필요 없이 홈 탭에 노출된 메뉴만 수집.
        """
        menu_items = []

        # 방법 1: 메뉴 섹션 내 아이템
        for container_sel in ["div.NSTUp", "ul.menu_list", "div[class*='menu']"]:
            container = await page.query_selector(container_sel)
            if not container:
                continue
            rows = await container.query_selector_all("li, div.menu_item")
            for row in rows:
                try:
                    # 메뉴명
                    name_el = await row.query_selector(
                        "span.lPzHi, span.menu_name, strong.menu_name, span.place_name"
                    )
                    name = (await name_el.inner_text()).strip() if name_el else ""

                    # 가격
                    price_el = await row.query_selector(
                        "span.GXS1X, em.price, span.price, span.place_money"
                    )
                    price = (await price_el.inner_text()).strip() if price_el else ""

                    if name:
                        menu_items.append({
                            "name": name,
                            "price": price,
                            "is_recommended": False,
                        })
                except Exception:
                    continue
            if menu_items:
                break

        # 방법 2: 대표메뉴 (홈 탭 노출)
        if not menu_items:
            try:
                reps = await page.query_selector_all("li.c1uwk, li.place_represent_menu")
                for item in reps:
                    name_el = await item.query_selector("span, strong")
                    price_el = await item.query_selector("em, small")
                    name = (await name_el.inner_text()).strip() if name_el else ""
                    price = (await price_el.inner_text()).strip() if price_el else ""
                    if name:
                        menu_items.append({"name": name, "price": price, "is_recommended": True})
            except Exception:
                pass

        result["menus"] = menu_items[:20]  # 최대 20개

    # ── 사진 수 ──────────────────────────────────────────────────────────────

    async def _parse_photos(self, page: Page, result: dict) -> None:
        """사진 수 파싱 (노출된 숫자 또는 갤러리 아이템 수)."""
        # 방법 1: "사진 N장" 텍스트
        for sel in ["a:has-text('사진') em", "span.photo_count", "a[href*='photo'] em"]:
            el = await page.query_selector(sel)
            if el:
                raw = re.sub(r'[^\d]', '', (await el.inner_text()).strip())
                if raw.isdigit():
                    result["photo_count"] = int(raw)
                    return

        # 방법 2: 갤러리 이미지 수 세기
        try:
            imgs = await page.query_selector_all("div.place_section img[src*='pstatic']")
            if imgs:
                result["photo_count"] = len(imgs)
        except Exception:
            pass
