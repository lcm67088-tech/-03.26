#!/usr/bin/env python3
"""
crawl_test.py — 크롤러 단독 실행 테스트
──────────────────────────────────────────────────────────────────────────────
Celery / DB 없이 Playwright 크롤러를 직접 실행해 결과를 확인한다.

사용법:
    # 가상환경 활성화 후 backend/ 디렉토리에서:
    cd backend
    python crawl_test.py

    # 특정 ID / URL로 테스트:
    python crawl_test.py --place 1005166855
    python crawl_test.py --place https://m.place.naver.com/restaurant/19797085

    # 순위 체크:
    python crawl_test.py --keyword "강남 맛집" --mid 1005166855

    # 전체 수집 (place info + 순위 체크):
    python crawl_test.py --full --place 1005166855 --keyword "강남 맛집"

    # 결과를 JSON 파일로 저장:
    python crawl_test.py --place 1005166855 --out result.json

의존성 (backend/requirements.txt):
    playwright>=1.44.0
    fake-useragent>=1.5.1

첫 실행 전 Playwright 브라우저 설치 필요:
    playwright install chromium
──────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

# ── 로깅 설정 ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("crawl_test")

# ── 프로젝트 루트를 sys.path에 추가 ──────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ─────────────────────────────────────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

def _parse_place_id(value: str) -> str:
    """URL이든 숫자든 place_id 추출."""
    from app.utils.naver import extract_naver_place_id
    pid = extract_naver_place_id(value)
    if not pid:
        print(f"❌ place_id 추출 실패: {value!r}")
        sys.exit(1)
    return pid


def _print_json(data: dict, title: str = "") -> None:
    if title:
        print(f"\n{'─'*60}")
        print(f"  {title}")
        print(f"{'─'*60}")
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _save_json(data: dict, path: str) -> None:
    out = Path(path)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ 결과 저장: {out.resolve()}")


# ─────────────────────────────────────────────────────────────────────────────
# 테스트 1: URL 파싱 (Playwright 불필요)
# ─────────────────────────────────────────────────────────────────────────────

def test_url_parsing() -> None:
    """다양한 URL 패턴에서 place_id 추출 검증."""
    from app.utils.naver import extract_naver_place_id, build_mobile_place_url

    cases = [
        ("https://map.naver.com/v5/entry/place/1005166855",      "1005166855"),
        ("https://map.naver.com/p/entry/place/1005166855",       "1005166855"),
        ("https://m.place.naver.com/restaurant/19797085",        "19797085"),
        ("https://m.place.naver.com/restaurant/19797085/home",   "19797085"),
        ("https://m.place.naver.com/place/1005166855",           "1005166855"),
        ("https://place.naver.com/restaurant/19797085",          "19797085"),
        ("1138220842",                                            "1138220842"),
    ]

    print("\n[URL 파싱 테스트]")
    all_ok = True
    for url, expected in cases:
        result = extract_naver_place_id(url)
        ok = result == expected
        status = "✅" if ok else "❌"
        print(f"  {status}  {url[:60]:<62}  →  {result}  (기대: {expected})")
        if not ok:
            all_ok = False

    # 모바일 URL 생성 확인
    mobile = build_mobile_place_url("1005166855")
    print(f"\n  모바일 URL 생성: {mobile}")

    if all_ok:
        print("\n✅ 모든 URL 파싱 테스트 통과!")
    else:
        print("\n❌ 일부 URL 파싱 실패!")


# ─────────────────────────────────────────────────────────────────────────────
# 테스트 2: 플레이스 기본 정보 수집
# ─────────────────────────────────────────────────────────────────────────────

async def test_place_info(place_id: str, proxy: dict | None = None) -> dict:
    """fetch_place_info() 실행 및 결과 출력."""
    from workers.crawler.place_info import fetch_place_info, PlaceNotFoundError, PlaceInfoError

    print(f"\n[플레이스 정보 수집] place_id={place_id}")
    print(f"  URL: https://m.place.naver.com/place/{place_id}/home")
    print("  크롤링 중... (30초 ~ 60초 소요될 수 있습니다)")

    t0 = time.time()
    try:
        result = await fetch_place_info(place_id, proxy=proxy)
        elapsed = time.time() - t0

        print(f"\n✅ 수집 완료! ({elapsed:.1f}초)")
        print(f"  상호명    : {result.get('name', '–')}")
        print(f"  카테고리  : {result.get('category', '–')}")
        print(f"  주소      : {result.get('address', '–')}")
        print(f"  전화번호  : {result.get('phone', '–')}")
        print(f"  홈페이지  : {result.get('homepage', '–')}")
        print(f"  방문자리뷰: {result.get('review_count', 0):,}개")
        print(f"  평점      : {result.get('avg_rating', 0.0)}")
        print(f"  블로그리뷰: {result.get('blog_review_count', 0):,}개")
        print(f"  저장수    : {result.get('saved_count', 0):,}")
        print(f"  월방문자  : {result.get('visitor_monthly', 0):,}")
        print(f"  사진수    : {result.get('photo_count', 0)}")
        print(f"  메뉴수    : {len(result.get('menus', []))}")
        print(f"  영업시간  : {len(result.get('hours', []))}요일 수집")
        print(f"  파워링크  : {'✅ 노출 중' if result.get('ad_power_link') else '없음'}")
        print(f"  플레이스광고: {'✅ 노출 중' if result.get('ad_place_ad') else '없음'}")

        if result.get("menus"):
            print(f"\n  [메뉴 목록 (최대 5개)]")
            for m in result["menus"][:5]:
                star = "★ " if m.get("is_recommended") else "  "
                print(f"    {star}{m['name']}  {m.get('price', '–')}")

        if result.get("hours"):
            print(f"\n  [영업시간]")
            for h in result["hours"]:
                if h.get("is_holiday"):
                    print(f"    {h['day_ko']} 휴무")
                else:
                    print(f"    {h['day_ko']} {h.get('open','?')} ~ {h.get('close','?')}")

        if result.get("raw_errors"):
            print(f"\n  ⚠️ 파싱 실패 항목: {result['raw_errors']}")

        return result

    except PlaceNotFoundError as e:
        elapsed = time.time() - t0
        print(f"\n❌ 플레이스 없음 ({elapsed:.1f}초): {e}")
        return {"error": str(e), "place_id": place_id}

    except PlaceInfoError as e:
        elapsed = time.time() - t0
        print(f"\n❌ 수집 실패 ({elapsed:.1f}초): {e}")
        return {"error": str(e), "place_id": place_id}

    except Exception as e:
        elapsed = time.time() - t0
        print(f"\n❌ 예외 발생 ({elapsed:.1f}초): {type(e).__name__}: {e}")
        return {"error": str(e), "place_id": place_id}


# ─────────────────────────────────────────────────────────────────────────────
# 테스트 3: 키워드 순위 체크
# ─────────────────────────────────────────────────────────────────────────────

async def test_rank_check(keyword: str, mid: str, max_rank: int = 5, proxy: dict | None = None) -> dict:
    """check_single_keyword() 실행 및 결과 출력."""
    from workers.crawler.rank_checker import check_single_keyword, BotDetectedError

    print(f"\n[키워드 순위 체크]")
    print(f"  키워드  : {keyword!r}")
    print(f"  MID     : {mid}")
    print(f"  최대순위: {max_rank}위까지")
    print(f"  URL     : https://m.search.naver.com/search.naver?query={keyword}")
    print("  크롤링 중... (20초 ~ 40초 소요될 수 있습니다)")

    t0 = time.time()
    try:
        result = await check_single_keyword(keyword, mid, max_rank=max_rank, proxy=proxy)
        elapsed = time.time() - t0

        rank = result.get("rank")
        if rank:
            print(f"\n✅ 순위 발견! ({elapsed:.1f}초)")
            print(f"  순위      : {rank}위")
            print(f"  업체명    : {result.get('company_name', '–')}")
        else:
            print(f"\n⚠️  순위 미발견 ({elapsed:.1f}초)")

        print(f"  섹션존재  : {'✅' if result.get('section_exists') else '❌'}")
        print(f"  최상단    : {'✅' if result.get('is_top_section') else '❌'}")
        print(f"  CPC광고   : {result.get('cpc_count', 0)}개")
        print(f"  전체업체  : {result.get('total_places', 0)}개")
        print(f"  상태      : {result.get('status', '–')}")
        print(f"  봇탐지    : {'⚠️ 감지됨' if result.get('bot_blocked') else '✅ 정상'}")

        return result

    except BotDetectedError as e:
        elapsed = time.time() - t0
        print(f"\n🚫 봇 탐지 차단 ({elapsed:.1f}초): {e}")
        return {"error": str(e), "bot_blocked": True}

    except Exception as e:
        elapsed = time.time() - t0
        print(f"\n❌ 예외 발생 ({elapsed:.1f}초): {type(e).__name__}: {e}")
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# 테스트 4: stealth 브라우저 동작 확인 (네이버 접속 여부)
# ─────────────────────────────────────────────────────────────────────────────

async def test_stealth_browser() -> bool:
    """스텔스 브라우저가 네이버에 정상 접속하는지 확인."""
    from playwright.async_api import async_playwright
    from workers.crawler.stealth import build_stealth_context, new_stealth_page, safe_goto, is_bot_blocked

    # is_bot_blocked 는 rank_checker 에 있으므로 직접 임포트
    from workers.crawler.rank_checker import is_bot_blocked

    print("\n[스텔스 브라우저 테스트]")
    print("  네이버 모바일 접속 테스트...")

    pw = None
    browser = None
    try:
        pw = await async_playwright().start()
        browser, context = await build_stealth_context(pw)
        page = await new_stealth_page(context)

        ok = await safe_goto(page, "https://m.naver.com", wait_until="domcontentloaded")
        if not ok:
            print("  ❌ 네이버 접속 실패")
            return False

        title = await page.title()
        blocked = await is_bot_blocked(page)

        print(f"  페이지 타이틀: {title!r}")
        print(f"  봇 탐지 여부: {'🚫 차단됨' if blocked else '✅ 정상'}")

        # navigator.webdriver 확인
        webdriver_val = await page.evaluate("navigator.webdriver")
        print(f"  navigator.webdriver: {webdriver_val!r}  ({'✅ 정상 (undefined)' if not webdriver_val else '❌ 탐지 가능'})")

        # User-Agent 확인
        ua = await page.evaluate("navigator.userAgent")
        print(f"  User-Agent: {ua[:80]}...")

        return not blocked

    except Exception as e:
        print(f"  ❌ 스텔스 브라우저 오류: {e}")
        return False
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


# ─────────────────────────────────────────────────────────────────────────────
# 기본 테스트 대상 (인수 없이 실행 시)
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_PLACES = [
    "1005166855",   # https://m.place.naver.com/place/1005166855
    "19797085",     # https://m.place.naver.com/restaurant/19797085
]

DEFAULT_KEYWORD_TESTS = [
    # (keyword, mid)
    ("강남 맛집", "1005166855"),
]


# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────

async def main_async(args: argparse.Namespace) -> None:
    results: dict = {}

    # 1. URL 파싱 테스트 (항상 실행)
    test_url_parsing()

    # 2. 스텔스 브라우저 테스트
    if args.stealth or args.full:
        ok = await test_stealth_browser()
        results["stealth_browser"] = {"ok": ok}
        if not ok:
            print("\n⛔ 스텔스 브라우저 접속 실패. 크롤링 테스트를 중단합니다.")
            print("   playwright install chromium  명령으로 브라우저를 설치하세요.")
            return

    # 3. 플레이스 정보 수집 테스트
    if args.place or args.full:
        place_ids = [_parse_place_id(args.place)] if args.place else DEFAULT_PLACES
        proxy = {"server": args.proxy} if args.proxy else None

        results["place_info"] = {}
        for pid in place_ids:
            info = await test_place_info(pid, proxy=proxy)
            results["place_info"][pid] = info
            if args.verbose:
                _print_json(info, f"place_info raw [{pid}]")

    # 4. 순위 체크 테스트
    if args.keyword and args.mid:
        proxy = {"server": args.proxy} if args.proxy else None
        rank = await test_rank_check(
            args.keyword, _parse_place_id(args.mid),
            max_rank=args.max_rank, proxy=proxy
        )
        results["rank_check"] = rank
        if args.verbose:
            _print_json(rank, "rank_check raw")

    elif args.full:
        proxy = {"server": args.proxy} if args.proxy else None
        results["rank_checks"] = []
        for kw, mid in DEFAULT_KEYWORD_TESTS:
            rank = await test_rank_check(kw, mid, proxy=proxy)
            results["rank_checks"].append(rank)

    # 5. 결과 저장
    if args.out:
        _save_json(results, args.out)

    # 요약
    print(f"\n{'='*60}")
    print("  테스트 완료 요약")
    print(f"{'='*60}")
    if "stealth_browser" in results:
        s = results["stealth_browser"]
        print(f"  스텔스 브라우저  : {'✅ 정상' if s['ok'] else '❌ 실패'}")
    if "place_info" in results:
        for pid, info in results["place_info"].items():
            ok = "error" not in info
            name = info.get("name", "–")
            print(f"  플레이스 {pid}: {'✅ ' + name if ok else '❌ ' + info.get('error','?')[:40]}")
    if "rank_check" in results:
        r = results["rank_check"]
        rank = r.get("rank")
        print(f"  순위체크 [{args.keyword}]: {'✅ ' + str(rank) + '위' if rank else '⚠️  미발견'}")
    if "rank_checks" in results:
        for r in results["rank_checks"]:
            rank = r.get("rank")
            kw = r.get("keyword", "?")
            print(f"  순위체크 [{kw}]: {'✅ ' + str(rank) + '위' if rank else '⚠️  미발견'}")


def main():
    parser = argparse.ArgumentParser(
        description="네이버 플레이스 크롤러 단독 테스트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python crawl_test.py                          # URL 파싱 테스트만
  python crawl_test.py --stealth                # 브라우저 접속 테스트
  python crawl_test.py --place 1005166855       # 플레이스 정보 수집
  python crawl_test.py --place https://m.place.naver.com/restaurant/19797085
  python crawl_test.py --keyword "강남 맛집" --mid 1005166855
  python crawl_test.py --full                   # 전체 테스트
  python crawl_test.py --full --out result.json # 결과 저장
  python crawl_test.py --full --proxy http://127.0.0.1:8888
        """
    )
    parser.add_argument("--place",    help="플레이스 ID 또는 URL (정보 수집 테스트)")
    parser.add_argument("--keyword",  help="검색 키워드 (순위 체크 테스트)")
    parser.add_argument("--mid",      help="순위 체크할 플레이스 ID (--keyword와 함께 사용)")
    parser.add_argument("--max-rank", type=int, default=5, help="최대 순위 탐색 범위 (기본: 5)")
    parser.add_argument("--stealth",  action="store_true", help="스텔스 브라우저 접속 테스트만")
    parser.add_argument("--full",     action="store_true", help="전체 테스트 실행")
    parser.add_argument("--proxy",    help="프록시 서버 URL (예: http://127.0.0.1:8888)")
    parser.add_argument("--out",      help="결과를 저장할 JSON 파일 경로")
    parser.add_argument("--verbose",  action="store_true", help="raw JSON 결과도 출력")

    args = parser.parse_args()

    # 인수가 아무것도 없으면 URL 파싱 테스트만 실행
    if not any([args.place, args.keyword, args.stealth, args.full]):
        test_url_parsing()
        print("\n💡 사용법: python crawl_test.py --help")
        print("   실제 크롤링: python crawl_test.py --stealth  또는  --place <ID>")
        return

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
