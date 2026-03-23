"""
플랫폼 공통 상수 정의 (Sprint 3~)

플랜별 사용 한도, 기타 비즈니스 상수를 한 곳에서 관리.
"""
from typing import TypedDict


# ============================
# 플랜 한도 타입
# ============================

class PlanLimit(TypedDict):
    """구독 플랜별 사용 한도"""
    max_places: int       # 등록 가능한 장소 수
    max_keywords: int     # 등록 가능한 키워드 수
    crawl_per_day: int    # 일별 크롤링 횟수


# ============================
# 플랜별 한도 상수
# ============================

PLAN_LIMITS: dict[str, PlanLimit] = {
    "free": {
        "max_places": 1,
        "max_keywords": 5,
        "crawl_per_day": 1,
    },
    "starter": {
        "max_places": 5,
        "max_keywords": 30,
        "crawl_per_day": 2,
    },
    "pro": {
        "max_places": 20,
        "max_keywords": 100,
        "crawl_per_day": 4,
    },
    "enterprise": {
        "max_places": 999,
        "max_keywords": 999,
        "crawl_per_day": 4,
    },
}

# 기본값 (알 수 없는 플랜에 대한 fallback)
DEFAULT_PLAN_LIMIT: PlanLimit = {
    "max_places": 1,
    "max_keywords": 5,
    "crawl_per_day": 1,
}


def get_plan_limits(plan: str) -> PlanLimit:
    """
    플랜 이름으로 한도 딕셔너리 반환.
    알 수 없는 플랜은 free 한도 적용.
    """
    return PLAN_LIMITS.get(plan, DEFAULT_PLAN_LIMIT)


# ============================
# 페이지네이션 기본값
# ============================

DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 100

# ============================
# 크롤링 관련 상수
# ============================

NAVER_PLACE_BASE_URL = "https://map.naver.com/v5/entry/place/{place_id}"


# ============================
# Sprint 8: 플랜 가격 정책
# ============================

class PlanPrice(TypedDict):
    """플랜별 가격 (원 단위)"""
    monthly: int   # 월간 결제 금액
    yearly: int    # 연간 결제 시 월 환산 금액 (20% 할인)


PLAN_PRICES: dict[str, PlanPrice] = {
    "free": {
        "monthly": 0,
        "yearly": 0,
    },
    "starter": {
        "monthly": 29000,
        "yearly": 23200,    # 29000 × 0.8 = 23200 (연간 20% 할인)
    },
    "pro": {
        "monthly": 79000,
        "yearly": 63200,    # 79000 × 0.8 = 63200
    },
    "enterprise": {
        "monthly": 199000,
        "yearly": 159200,   # 199000 × 0.8 = 159200
    },
}

# 플랜 순서 (업/다운그레이드 비교용)
# 인덱스가 클수록 상위 플랜
PLAN_ORDER: list[str] = ["free", "starter", "pro", "enterprise"]


def get_plan_price(plan: str, billing_cycle: str) -> int:
    """
    플랜 + 결제 주기에 따른 월 금액 반환.
    알 수 없는 플랜/주기는 0원 반환.
    """
    prices = PLAN_PRICES.get(plan, {"monthly": 0, "yearly": 0})
    return prices.get(billing_cycle, 0)


def get_plan_rank(plan: str) -> int:
    """
    플랜의 순서(rank) 반환.
    높을수록 상위 플랜. 알 수 없는 플랜은 -1.
    """
    try:
        return PLAN_ORDER.index(plan)
    except ValueError:
        return -1
