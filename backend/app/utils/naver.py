"""
네이버 플레이스 관련 유틸리티 함수 (Sprint 9 업데이트)

지원 URL 패턴:
  1) https://map.naver.com/v5/entry/place/1234567
  2) https://map.naver.com/p/entry/place/1234567       (신버전 /p/ 경로)
  3) https://m.place.naver.com/restaurant/1138220842   (모바일 카테고리 포함)
  4) https://m.place.naver.com/restaurant/1138220842/home
  5) https://place.naver.com/restaurant/1138220842
  6) https://place.naver.com/1138220842                (숏폼)
  7) 숫자만 입력 (ID 직접 입력)
"""
import re
from urllib.parse import urlparse
from typing import Optional


# ============================
# URL 패턴 (우선순위 순)
# ============================

_PLACE_ID_PATTERNS = [
    # map.naver.com/v5 또는 /p 경로
    r'map\.naver\.com/(?:v5|p)/entry/place/(\d+)',
    # m.place.naver.com/{category}/{id}  또는 place.naver.com/{category}/{id}
    r'(?:m\.)?place\.naver\.com/[^/?#]+/(\d+)',
    # place.naver.com/{id}  (숏폼, 카테고리 없음)
    r'place\.naver\.com/(\d+)(?:[/?#]|$)',
]


def extract_naver_place_id(url: str) -> Optional[str]:
    """
    네이버 플레이스 URL에서 place_id(숫자) 추출.

    숫자만 입력해도 그대로 반환한다 (ID 직접 입력 지원).

    Args:
        url: 네이버 플레이스 URL 또는 ID 문자열

    Returns:
        추출된 place_id 문자열, 실패 시 None
    """
    s = url.strip()

    # 숫자만 입력한 경우 → ID로 직접 취급
    if s.isdigit():
        return s

    for pattern in _PLACE_ID_PATTERNS:
        match = re.search(pattern, s)
        if match:
            return match.group(1)

    return None


def build_naver_place_url(place_id: str) -> str:
    """
    place_id로 표준 네이버 플레이스 URL 생성.

    Args:
        place_id: 네이버 플레이스 ID

    Returns:
        표준 URL 문자열
    """
    return f"https://map.naver.com/v5/entry/place/{place_id}"


def build_mobile_place_url(place_id: str) -> str:
    """
    모바일 플레이스 URL 생성 (크롤링 시 사용).
    모바일 페이지가 파싱하기 더 단순한 구조를 가짐.
    """
    return f"https://m.place.naver.com/place/{place_id}/home"


def is_valid_naver_place_url(url: str) -> bool:
    """
    올바른 네이버 플레이스 URL인지 검증.

    Args:
        url: 검증할 URL 문자열 (숫자 ID도 허용)

    Returns:
        유효하면 True, 아니면 False
    """
    s = url.strip()

    # 숫자 ID 직접 입력
    if s.isdigit():
        return True

    # URL 형식 체크
    try:
        parsed = urlparse(s)
        if parsed.scheme not in ("http", "https"):
            return False
        if not parsed.netloc:
            return False
    except Exception:
        return False

    return extract_naver_place_id(s) is not None


def normalize_naver_place_url(url: str) -> Optional[str]:
    """
    다양한 형태의 URL을 표준 형식으로 정규화.

    Args:
        url: 원본 URL 또는 ID

    Returns:
        정규화된 URL, 실패 시 None
    """
    place_id = extract_naver_place_id(url)
    if not place_id:
        return None
    return build_naver_place_url(place_id)
