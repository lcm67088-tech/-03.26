"""
workers/crawler/stealth.py
──────────────────────────────────────────────────────────────────────────────
네이버 봇 탐지 우회 전략 모음

네이버가 사용하는 주요 봇 탐지 기법:
  1) navigator.webdriver 플래그 감지
  2) User-Agent 블랙리스트 (HeadlessChrome 등)
  3) CDP(Chrome DevTools Protocol) 흔적 감지
  4) 마우스/키보드 이벤트 부재 감지
  5) Canvas/WebGL fingerprint 비교
  6) 쿠키·세션 신뢰도 점수
  7) 요청 속도 / 패턴 분석 (Rate Limiting)
  8) TLS fingerprint (JA3) 분석

우회 전략:
  ① playwright-stealth 유사 JS 패치 (webdriver 플래그 제거)
  ② 실제 크롬 User-Agent 로테이션 (fake-useragent)
  ③ 인간형 마우스/스크롤/딜레이 시뮬레이션
  ④ 세션 쿠키 재사용 (로그인 불필요 구간)
  ⑤ 요청 간격 무작위 지연 (2~6초)
  ⑥ 뷰포트·타임존·언어 실제 값으로 설정

의존성:
  playwright>=1.44.0
  fake-useragent>=1.5.1
──────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import asyncio
import random
from typing import Optional

from fake_useragent import UserAgent
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)


# ── User-Agent 풀 (한번만 초기화) ────────────────────────────────────────────
_ua = UserAgent(browsers=["chrome"], os=["windows", "macos"], min_version=120.0)


# ── 실제 크롬 Accept-Language 목록 ───────────────────────────────────────────
_ACCEPT_LANGUAGES = [
    "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "ko,en-US;q=0.9,en;q=0.8",
    "ko-KR,ko;q=0.8,en;q=0.6",
]

# ── 실제 뷰포트 목록 ──────────────────────────────────────────────────────────
_VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1280, "height": 800},
]

# ── navigator.webdriver 제거 + CDP 흔적 제거 JS ───────────────────────────────
# Playwright 기본 설정만으로는 navigator.webdriver = true 가 남음
# 이를 init_script 로 페이지 로드 전에 패치한다
_STEALTH_JS = """
// 1. navigator.webdriver 제거
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
    configurable: true,
});

// 2. chrome 객체 주입 (HeadlessChrome에는 없음)
if (!window.chrome) {
    window.chrome = {
        app: { isInstalled: false },
        runtime: {},
        loadTimes: function() {},
        csi: function() {},
    };
}

// 3. permissions API 패치 (봇은 denied 고정으로 돌려줌)
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(parameters)
);

// 4. plugins 배열 채우기 (HeadlessChrome은 plugins 없음)
Object.defineProperty(navigator, 'plugins', {
    get: () => [
        { name: 'Chrome PDF Plugin',   filename: 'internal-pdf-viewer',    description: 'Portable Document Format' },
        { name: 'Chrome PDF Viewer',   filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
        { name: 'Native Client',       filename: 'internal-nacl-plugin',   description: '' },
    ],
    configurable: true,
});

// 5. languages 설정
Object.defineProperty(navigator, 'languages', {
    get: () => ['ko-KR', 'ko', 'en-US', 'en'],
    configurable: true,
});

// 6. WebGL 렌더러 정보 노출 방지
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    if (parameter === 37445) return 'Intel Inc.';           // UNMASKED_VENDOR_WEBGL
    if (parameter === 37446) return 'Intel Iris OpenGL Engine'; // UNMASKED_RENDERER_WEBGL
    return getParameter.call(this, parameter);
};

// 7. iframe contentWindow.navigator.webdriver 패치
const _iframeDescriptor = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'contentWindow');
Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
    get: function() {
        const win = _iframeDescriptor.get.call(this);
        if (win && win.navigator) {
            Object.defineProperty(win.navigator, 'webdriver', { get: () => undefined });
        }
        return win;
    },
    configurable: true,
});
"""


async def build_stealth_context(
    playwright: Playwright,
    proxy: Optional[dict] = None,
) -> tuple[Browser, BrowserContext]:
    """
    봇 탐지 우회 설정이 적용된 Playwright 브라우저 컨텍스트를 생성한다.

    Args:
        playwright: async_playwright() 인스턴스
        proxy: {"server": "http://ip:port"} 형식의 프록시 설정 (선택)

    Returns:
        (browser, context) 튜플
        - 호출자가 사용 후 반드시 browser.close() 해야 함

    스텔스 설정 요약:
        - headless=True  + --disable-blink-features=AutomationControlled
        - 랜덤 User-Agent (Chrome 120+, Windows/macOS)
        - 랜덤 뷰포트
        - 한국어 로케일 + 서울 타임존
        - init_script 로 webdriver/chrome/plugins/WebGL 패치
        - 프록시 지원 (IP 로테이션 연동 시)
    """
    ua = _ua.random
    viewport = random.choice(_VIEWPORTS)
    accept_language = random.choice(_ACCEPT_LANGUAGES)

    launch_args = [
        # 핵심: 자동화 플래그 제거
        "--disable-blink-features=AutomationControlled",
        # GPU 비활성화 (서버 환경)
        "--disable-gpu",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        # 불필요한 기능 비활성화
        "--disable-extensions",
        "--disable-default-apps",
        "--disable-sync",
        "--disable-translate",
        "--hide-scrollbars",
        "--metrics-recording-only",
        "--mute-audio",
        "--no-first-run",
        "--safebrowsing-disable-auto-update",
        # 렌더링 최적화 (서버)
        "--disable-software-rasterizer",
        "--disable-background-networking",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-breakpad",
        "--disable-client-side-phishing-detection",
        "--disable-component-update",
        "--disable-domain-reliability",
        "--disable-features=AudioServiceOutOfProcess",
        "--disable-hang-monitor",
        "--disable-ipc-flooding-protection",
        "--disable-prompt-on-repost",
        "--disable-renderer-backgrounding",
        "--disable-setuid-sandbox",
        "--force-color-profile=srgb",
        "--disable-web-security",   # CORS 우회 (수집 전용)
    ]

    launch_kwargs = dict(
        headless=True,
        args=launch_args,
        chromium_sandbox=False,
    )
    if proxy:
        launch_kwargs["proxy"] = proxy

    browser = await playwright.chromium.launch(**launch_kwargs)

    context = await browser.new_context(
        user_agent=ua,
        viewport=viewport,
        locale="ko-KR",
        timezone_id="Asia/Seoul",
        accept_downloads=False,
        java_script_enabled=True,
        extra_http_headers={
            "Accept-Language": accept_language,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Upgrade-Insecure-Requests": "1",
        },
        # 이미지·폰트 차단 → 로딩 속도 개선 (순위/텍스트 수집에는 불필요)
        # 필요 시 주석 해제
        # bypass_csp=True,
    )

    # webdriver/chrome/plugins/WebGL 패치 — 모든 페이지에 자동 적용
    await context.add_init_script(_STEALTH_JS)

    return browser, context


async def new_stealth_page(context: BrowserContext) -> Page:
    """
    컨텍스트에서 새 스텔스 페이지를 생성한다.
    - 불필요한 리소스(이미지, 폰트, 미디어) 차단 → 속도 향상
    - 자동화 감지 헤더 추가 차단
    """
    page = await context.new_page()

    # 리소스 필터링: 이미지·폰트·미디어는 차단, JS·XHR·document는 허용
    async def _block_resources(route):
        if route.request.resource_type in ("image", "font", "media", "stylesheet"):
            await route.abort()
        else:
            await route.continue_()

    await page.route("**/*", _block_resources)

    return page


# ── 인간형 행동 시뮬레이션 헬퍼 ──────────────────────────────────────────────

async def human_delay(min_ms: int = 800, max_ms: int = 2500) -> None:
    """
    실제 사람처럼 무작위 대기.
    기본값: 0.8 ~ 2.5초
    """
    ms = random.randint(min_ms, max_ms)
    await asyncio.sleep(ms / 1000)


async def human_scroll(page: Page, steps: int = 3) -> None:
    """
    페이지를 천천히 자연스럽게 스크롤.
    - 단순 scrollTo 대신 여러 번 나눠서 스크롤
    - 각 스텝 사이에 짧은 딜레이
    """
    for _ in range(steps):
        delta = random.randint(200, 600)
        await page.mouse.wheel(0, delta)
        await asyncio.sleep(random.uniform(0.15, 0.45))


async def human_mouse_move(page: Page) -> None:
    """
    마우스를 화면 중앙 근처로 무작위 이동.
    완전히 움직임이 없으면 봇으로 탐지될 수 있음.
    """
    x = random.randint(400, 1200)
    y = random.randint(200, 700)
    await page.mouse.move(x, y, steps=random.randint(5, 15))
    await asyncio.sleep(random.uniform(0.1, 0.3))


async def safe_goto(
    page: Page,
    url: str,
    timeout: int = 30_000,
    wait_until: str = "domcontentloaded",
) -> bool:
    """
    페이지 이동 + 에러 처리 래퍼.

    Args:
        page: Playwright 페이지
        url: 이동할 URL
        timeout: 타임아웃 (ms)
        wait_until: 대기 조건 (domcontentloaded / networkidle / load)

    Returns:
        성공 시 True, 실패(타임아웃/404/봇차단) 시 False
    """
    try:
        response = await page.goto(url, timeout=timeout, wait_until=wait_until)
        if response is None:
            return False
        # 4xx/5xx → 실패
        if response.status >= 400:
            return False
        return True
    except Exception:
        return False
