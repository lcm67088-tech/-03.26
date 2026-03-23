"""
naver_place_parser.py  v5.0
============================
httpx 기반 네이버 플레이스 정보 파서 (크롬 불필요)
__APOLLO_STATE__ JSON 직접 파싱 + asyncio 병렬 요청 + GraphQL 페이지네이션

■ v5.0 변경 사항 (v4.0 → v5.0)
  - 블로그 리뷰: GraphQL API fsasReviews(input) page=0,1,2... 실제 페이지네이션
    → SSR Apollo ?page=N 방식 완전 폐기 (항상 첫 페이지만 반환)
    → maxItemCount 기준으로 필요한 만큼 GraphQL 호출
    → max_blog_reviews=100 기본 (최대 1000 설정 가능)
  - 영수증 리뷰: URL ?item=CURSOR 방식 커서 페이지네이션
    → 첫 페이지: Apollo SSR에서 items + cursor 추출
    → 추가 페이지: ?item=CURSOR URL로 Apollo 재파싱 → 새 cursor
    → 중복 ID 체크로 안전한 무한루프 방지
    → max_visitor_reviews=100 기본
  - 사진: Apollo sasImages + images(ugcModeling) + cpImages + menuImages
    → 업종별 소스 자동 선택 (restaurant/accommodation: sasImages 우선)
    → hairshop/nailshop: ugcModeling 사진 수집
    → hospital/place: cpImages 수집
    → 모든 소스 합산 후 중복 URL 제거
    → max_photos=200 기본

■ 추출 항목
  기본정보   : name, category, roadAddress, address, phone, mid, x, y
  대표키워드  : keyword_list
  테마태그    : themes
  소개글      : introduction
  리뷰수      : visitor_review_count, blog_review_total
  영수증리뷰  : visitor_reviews (최대 max_visitor_reviews건)
                – id, rating, body, images, item, author, visited, originType, tags, cursor
  블로그리뷰  : blog_reviews (최대 max_blog_reviews건, GraphQL pagination)
                – type, url, title, contents, thumbnails, date, authorName, reviewId, rank
                  (+ full_images, full_text if fetch_blog_content=True)
  메뉴        : menus (업종별 분기)
  영업시간    : business_hours (status, description, days, regular_closed, free_text)
  편의시설    : conveniences
  사진        : photos (최대 max_photos건, 다중 소스 합산)
                – rank, originalUrl, imgUrl, title, section, date, link, authorName
  정적지도    : static_map_url
"""

import asyncio
import httpx
import json
import re
import time
from typing import Optional


# ─────────────────────────────────────────────
# 상수
# ─────────────────────────────────────────────

_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)
_HEADERS = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://m.place.naver.com/",
}
_GQL_HEADERS = {
    "User-Agent": _UA,
    "Accept": "*/*",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Content-Type": "application/json",
    "Referer": "https://m.place.naver.com/",
    "Origin": "https://m.place.naver.com",
}
_GQL_ENDPOINT = "https://api.place.naver.com/graphql"

_TAB_SUFFIX = {
    "home":   "",
    "review": "/review/visitor",
    "ugc":    "/review/ugc",
    "info":   "/information",
    "photo":  "/photo",
    "menu":   "/menu/list",
}

# 메뉴 없는 업종
_NO_MENU_CATEGORIES = {"accommodation", "hospital"}


# ─────────────────────────────────────────────
# URL / 이미지 헬퍼
# ─────────────────────────────────────────────

def _img_clean(url: str) -> str:
    """썸네일 쿼리스트링 제거"""
    if not url:
        return url
    return url.split("?type=")[0].rstrip("...").strip()


def _tab_url(place_id: str, category: str, tab: str) -> str:
    return f"https://m.place.naver.com/{category}/{place_id}" + _TAB_SUFFIX.get(tab, "")


def _visitor_url(place_id: str, category: str, cursor: Optional[str] = None) -> str:
    base = f"https://m.place.naver.com/{category}/{place_id}/review/visitor"
    if cursor:
        return f"{base}?item={cursor}"
    return base


# ─────────────────────────────────────────────
# Apollo State 파싱 헬퍼
# ─────────────────────────────────────────────

def _extract_apollo(html: str) -> dict:
    idx = html.find("window.__APOLLO_STATE__")
    if idx == -1:
        return {}
    start = html.find("{", idx)
    if start == -1:
        return {}
    depth = 0
    for i, ch in enumerate(html[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start: i + 1])
                except json.JSONDecodeError:
                    return {}
    return {}


def _ref(apollo: dict, val) -> dict:
    if isinstance(val, dict) and "__ref" in val:
        return apollo.get(val["__ref"], {})
    return val if isinstance(val, dict) else {}


def _place_detail(apollo: dict) -> dict:
    rq = apollo.get("ROOT_QUERY", {})
    for k, v in rq.items():
        if "placeDetail" in k and isinstance(v, dict):
            return v
    return {}


# ─────────────────────────────────────────────
# 개별 파싱 함수
# ─────────────────────────────────────────────

def _parse_base(apollo: dict, place_id: str) -> dict:
    base = apollo.get(f"PlaceDetailBase:{place_id}", {})
    coord = base.get("coordinate") or {}
    if isinstance(coord, dict) and "__ref" in coord:
        coord = apollo.get(coord["__ref"], {})
    return {
        "mid":         place_id,
        "name":        base.get("name", ""),
        "category":    base.get("category", ""),
        "roadAddress": base.get("roadAddress", ""),
        "address":     base.get("address", ""),
        "phone":       base.get("phone", ""),
        "x":           coord.get("x", ""),
        "y":           coord.get("y", ""),
    }


def _parse_keyword_list(html: str) -> list:
    m = re.search(r'"keywordList"\s*:\s*\[([^\]]+)\]', html)
    if m:
        return re.findall(r'"([^"]+)"', m.group(1))[:5]
    return []


def _parse_themes(apollo: dict) -> list:
    pd = _place_detail(apollo)
    themes = pd.get("themes", [])
    if not isinstance(themes, list):
        return []
    result = []
    for t in themes:
        if isinstance(t, str):
            result.append(t)
        elif isinstance(t, dict):
            val = t.get("name") or t.get("text", "")
            if val:
                result.append(val)
    return result


def _parse_description(apollo: dict) -> str:
    rq = apollo.get("ROOT_QUERY", {})
    for rk, rv in rq.items():
        if "placeDetail" not in rk or not isinstance(rv, dict):
            continue
        for dk, dv in rv.items():
            if dk.startswith("description") and isinstance(dv, str) and dv.strip():
                return dv.strip()
    return ""


def _parse_static_map_url(apollo: dict) -> str:
    rq = apollo.get("ROOT_QUERY", {})
    for rk, rv in rq.items():
        if "placeDetail" not in rk or not isinstance(rv, dict):
            continue
        for dk, dv in rv.items():
            if dk.startswith("staticMapUrl") and isinstance(dv, str) and dv.strip():
                return dv.strip()
    return ""


def _parse_review_counts(
    apollo_home: dict, apollo_review: dict, apollo_ugc: dict, place_id: str
) -> dict:
    """영수증 리뷰 총수, 블로그 리뷰 총수"""
    # 영수증 리뷰 총수
    visitor_total = 0
    for k, v in apollo_review.get("ROOT_QUERY", {}).items():
        if "visitorReviews" in k and isinstance(v, dict):
            t = v.get("total", 0) or 0
            if t > visitor_total:
                visitor_total = t
    if not visitor_total:
        vr_stats = apollo_home.get(f"VisitorReviewStatsResult:{place_id}", {})
        visitor_total = (
            vr_stats.get("visitorReviewsTotal")
            or apollo_home.get(f"PlaceDetailBase:{place_id}", {}).get("visitorReviewsTotal", 0)
            or 0
        )

    # 블로그 리뷰 총수 + maxItemCount
    blog_total = 0
    blog_max_item = 0
    blog_params = {}
    for k, v in apollo_ugc.get("ROOT_QUERY", {}).items():
        if "fsasReviews" not in k or not isinstance(v, dict):
            continue
        t = v.get("total", 0) or 0
        if '"buyWithMyMoneyType":true' in k or '"buyWithMyMoney":true' in k:
            continue
        if t > blog_total:
            blog_total = t
            blog_max_item = v.get("maxItemCount", 0) or 0
            # 파라미터 추출
            m = re.search(r'fsasReviews\((\{.*?\})\)', k)
            if m:
                try:
                    raw = json.loads(m.group(1))
                    blog_params = raw.get("input", raw)
                except Exception:
                    pass

    if not blog_total:
        pd = _place_detail(apollo_home)
        for k, v in pd.items():
            if "fsasReviews" in k and isinstance(v, dict):
                t = v.get("total", 0) or 0
                if t > blog_total:
                    blog_total = t

    return {
        "visitor_review_count": visitor_total,
        "blog_review_total":    blog_total,
        "_blog_max_item_count": blog_max_item,
        "_blog_gql_params":     blog_params,
    }


def _parse_visitor_page(apollo: dict, seen_ids: set, max_count: int) -> tuple[list, str | None]:
    """
    단일 Apollo에서 visitorReviews 아이템 파싱.
    반환: (리뷰 목록, 마지막 cursor)
    """
    reviews = []
    last_cursor = None
    rq = apollo.get("ROOT_QUERY", {})

    # 가장 많은 total을 가진 키 우선
    sorted_keys = sorted(
        [(k, v) for k, v in rq.items()
         if "visitorReviews" in k and isinstance(v, dict)],
        key=lambda x: x[1].get("total", 0) or 0,
        reverse=True,
    )

    for k, v in sorted_keys:
        items_list = v.get("items") or []
        for item in items_list:
            if not (isinstance(item, dict) and "__ref" in item):
                continue
            rv = apollo.get(item["__ref"], {})
            if not rv:
                continue

            rv_id = rv.get("id") or rv.get("reviewId") or item["__ref"]
            cursor = rv.get("cursor", "")
            if cursor:
                last_cursor = cursor

            if rv_id in seen_ids:
                continue
            seen_ids.add(rv_id)

            if len(reviews) >= max_count:
                break

            author_obj = _ref(apollo, rv.get("author", {}))
            nickname = (
                author_obj.get("nickname", "")
                or author_obj.get("name", "")
                or rv.get("nickname", "")
            )

            # 이미지
            images = []
            for m_item in (rv.get("media") or []):
                if isinstance(m_item, dict):
                    raw = m_item.get("thumbnail", "") or m_item.get("url", "")
                    if raw:
                        images.append(_img_clean(raw))
                elif isinstance(m_item, str) and m_item:
                    images.append(_img_clean(m_item))
            thumb = rv.get("thumbnail", "")
            if thumb and not images:
                images.append(_img_clean(thumb))

            # 주문 메뉴
            item_obj = rv.get("item") or {}
            item_name = item_obj.get("name", "") if isinstance(item_obj, dict) else ""

            # 태그
            tags = []
            for t in (rv.get("tags") or []):
                if isinstance(t, dict):
                    label = t.get("label") or t.get("text") or t.get("name", "")
                    if label:
                        tags.append(label)
                elif isinstance(t, str):
                    tags.append(t)

            reviews.append({
                "id":         rv_id,
                "rating":     rv.get("rating", 0),
                "body":       rv.get("body", ""),
                "originType": rv.get("originType", ""),
                "item":       item_name,
                "author":     nickname,
                "visited":    rv.get("visited", ""),
                "created":    rv.get("created", ""),
                "viewCount":  rv.get("viewCount", 0),
                "images":     images,
                "tags":       tags,
                "cursor":     cursor,
            })

        if len(reviews) >= max_count:
            break

    return reviews, last_cursor


def _parse_blog_page(apollo: dict, seen_ids: set, max_count: int) -> list:
    """단일 Apollo에서 fsasReviews(buyWithMyMoney:false) 파싱"""
    reviews = []
    rq = apollo.get("ROOT_QUERY", {})

    # buyWithMyMoney:true 제외하고 total 최대 키
    target_key = None
    target_total = 0
    for k, v in rq.items():
        if "fsasReviews" not in k or not isinstance(v, dict):
            continue
        t = v.get("total", 0) or 0
        if '"buyWithMyMoneyType":true' in k or '"buyWithMyMoney":true' in k:
            continue
        if t > target_total:
            target_total = t
            target_key = k

    # fallback
    if not target_key:
        for k, v in rq.items():
            if "fsasReviews" in k and isinstance(v, dict):
                t = v.get("total", 0) or 0
                if t > target_total:
                    target_total = t
                    target_key = k

    def _collect_direct(ap):
        result = []
        for k, v in ap.items():
            if not (k.startswith("FsasReview:") and isinstance(v, dict)):
                continue
            rid = v.get("reviewId", "") or k
            if rid in seen_ids:
                continue
            if len(result) + len(reviews) >= max_count:
                break
            seen_ids.add(rid)
            raw_list = v.get("thumbnailUrlList") or []
            if not raw_list and v.get("thumbnailUrl"):
                raw_list = [v["thumbnailUrl"]]
            thumbnails = [_img_clean(u) for u in raw_list if u]
            result.append({
                "type":            v.get("type", ""),
                "typeName":        v.get("typeName", ""),
                "url":             v.get("url", ""),
                "home":            v.get("home", ""),
                "title":           v.get("title", ""),
                "contents":        v.get("contents", ""),
                "authorName":      v.get("authorName", ""),
                "date":            v.get("date", ""),
                "createdString":   v.get("createdString", ""),
                "reviewId":        rid,
                "thumbnails":      thumbnails,
                "thumbnailCount":  v.get("thumbnailCount", 0),
                "profileImageUrl": v.get("profileImageUrl", ""),
                "rank":            v.get("rank"),
            })
        return result

    if not target_key:
        return sorted(_collect_direct(apollo), key=lambda r: r.get("rank") or 9999)

    items_list = rq[target_key].get("items") or []
    if not items_list:
        return sorted(_collect_direct(apollo), key=lambda r: r.get("rank") or 9999)

    for item in items_list:
        if len(reviews) >= max_count:
            break
        if not (isinstance(item, dict) and "__ref" in item):
            continue
        v = apollo.get(item["__ref"], {})
        if not v:
            continue
        rid = v.get("reviewId", "") or item["__ref"]
        if rid in seen_ids:
            continue
        seen_ids.add(rid)

        raw_list = v.get("thumbnailUrlList") or []
        if not raw_list and v.get("thumbnailUrl"):
            raw_list = [v["thumbnailUrl"]]
        thumbnails = [_img_clean(u) for u in raw_list if u]

        reviews.append({
            "type":            v.get("type", ""),
            "typeName":        v.get("typeName", ""),
            "url":             v.get("url", ""),
            "home":            v.get("home", ""),
            "title":           v.get("title", ""),
            "contents":        v.get("contents", ""),
            "authorName":      v.get("authorName", ""),
            "date":            v.get("date", ""),
            "createdString":   v.get("createdString", ""),
            "reviewId":        rid,
            "thumbnails":      thumbnails,
            "thumbnailCount":  v.get("thumbnailCount", 0),
            "profileImageUrl": v.get("profileImageUrl", ""),
            "rank":            v.get("rank"),
        })

    return reviews


def _parse_business_hours(apollo_info: dict) -> dict:
    rq = apollo_info.get("ROOT_QUERY", {})
    for rk, rv in rq.items():
        if "placeDetail" not in rk or not isinstance(rv, dict):
            continue
        for dk, dv in rv.items():
            if "newBusinessHours" not in dk or not isinstance(dv, list) or not dv:
                continue
            bh = dv[0]
            status_obj = bh.get("businessStatusDescription") or {}
            status_text = status_obj.get("status", "")
            status_desc = status_obj.get("description", "")

            days = []
            for h in (bh.get("businessHours") or []):
                bhr = h.get("businessHours") or {}
                brk_list = h.get("breakHours") or []
                lo_list  = h.get("lastOrderTimes") or []

                brk_start = brk_end = None
                if brk_list and isinstance(brk_list[0], dict):
                    brk = brk_list[0]
                    s = brk.get("breakHours") or {}
                    brk_start = s.get("start")
                    brk_end   = s.get("end")

                last_order = None
                if lo_list and isinstance(lo_list[0], dict):
                    lo = lo_list[0].get("lastOrderTime") or {}
                    last_order = lo.get("start")

                days.append({
                    "day":         h.get("day", ""),
                    "open":        bhr.get("start", ""),
                    "close":       bhr.get("end", ""),
                    "break_start": brk_start,
                    "break_end":   brk_end,
                    "last_order":  last_order,
                    "closed":      h.get("description") == "휴무일",
                })

            return {
                "status":         status_text,
                "description":    status_desc,
                "days":           days,
                "regular_closed": bh.get("comingRegularClosedDays", "") or "",
                "free_text":      bh.get("freeText", "") or "",
            }
    return {}


def _parse_conveniences(apollo_info: dict, place_id: str) -> list:
    result = []
    seen   = set()

    # PlaceDetailBase.conveniences
    pdb = apollo_info.get(f"PlaceDetailBase:{place_id}", {})
    for c in (pdb.get("conveniences") or []):
        if isinstance(c, str):
            if c not in seen:
                seen.add(c)
                result.append(c)
        elif isinstance(c, dict):
            if "__ref" in c:
                obj = apollo_info.get(c["__ref"], {})
                name = obj.get("name") or obj.get("i18nName", "")
            else:
                name = c.get("name") or c.get("i18nName", "")
            if name and name not in seen:
                seen.add(name)
                result.append(name)

    # InformationFacilities 타입 직접 수집
    for k, v in apollo_info.items():
        if k.startswith("InformationFacilities:") and isinstance(v, dict):
            name = v.get("name") or v.get("i18nName", "")
            if name and name not in seen:
                seen.add(name)
                result.append(name)

    return result


def _parse_photos_from_apollo(apollo: dict, seen_urls: set, max_count: int) -> list:
    """
    단일 Apollo에서 사진 수집.
    소스 우선순위: sasImages > images(ugcModeling) > cpImages > menuImages > Media
    """
    photos = []
    rq = apollo.get("ROOT_QUERY", {})

    def _add(orig, img_url, title="", section="", date="", link="", author="",
             width="", height="", text="", subsection="", rank=""):
        if not orig or orig in seen_urls or len(photos) >= max_count:
            return
        seen_urls.add(orig)
        photos.append({
            "rank":        rank,
            "originalUrl": orig,
            "imgUrl":      img_url or orig,
            "title":       title or "",
            "text":        text or "",
            "section":     section or "",
            "subsection":  subsection or "",
            "date":        date or "",
            "link":        link or "",
            "authorName":  author or "",
            "width":       width or "",
            "height":      height or "",
        })

    for rk, rv in rq.items():
        if "placeDetail" not in rk or not isinstance(rv, dict):
            continue
        for dk, dv in rv.items():

            # ── sasImages (식당/숙박/카페 등) ─────────────────────────
            if dk.startswith("sasImages") and isinstance(dv, list) and dv:
                for img in (dv[0].get("items") or []):
                    if not isinstance(img, dict):
                        continue
                    orig = img.get("originalUrl") or img.get("imgUrl") or ""
                    _add(orig, img.get("imgUrl") or orig,
                         img.get("title", ""), img.get("section", ""),
                         img.get("date", ""), img.get("link", ""),
                         img.get("authorname", ""), str(img.get("width", "") or ""),
                         str(img.get("height", "") or ""), img.get("text", ""),
                         img.get("subsection", ""), str(img.get("rank", "") or ""))

            # ── images(ugcModeling) (미용 업종) ───────────────────────
            # elif이 아닌 if로 → sasImages 없을 때도 독립 처리
            if "ugcModeling" in dk and isinstance(dv, dict):
                raw_imgs = dv.get("images") or dv.get("items") or []
                for img in raw_imgs:
                    if isinstance(img, dict) and "__ref" in img:
                        img = apollo.get(img["__ref"], {})
                    if not isinstance(img, dict):
                        continue
                    # url 필드가 None일 수 있으므로 origin 우선 사용
                    orig = (img.get("origin") or img.get("url") or
                            img.get("originalUrl") or "")
                    if not orig:
                        continue
                    thumb = img.get("thumbnail") or orig
                    _add(orig, thumb,
                         img.get("infoTitle") or img.get("desc") or "",
                         "ugc", "", "", "",
                         str(img.get("width") or ""), str(img.get("height") or ""))

            # ── cpImages (업체 등록 이미지) ────────────────────────────
            if "cpImages" in dk and isinstance(dv, dict):
                raw_imgs = dv.get("images") or dv.get("items") or []
                for img in raw_imgs:
                    if isinstance(img, dict) and "__ref" in img:
                        img = apollo.get(img["__ref"], {})
                    if not isinstance(img, dict):
                        continue
                    orig = (img.get("originalUrl") or img.get("url") or
                            img.get("imgUrl") or "")
                    if not orig:
                        continue
                    _add(orig, img.get("imgUrl") or img.get("url") or orig,
                         img.get("title") or img.get("name") or "",
                         "owner", img.get("date") or "", "", "",
                         str(img.get("width") or ""), str(img.get("height") or ""))

            # ── images(source) — 브랜드/업체 이미지 (ugcModeling 제외) ─
            if (dk.startswith("images(") and isinstance(dv, dict)
                    and "ugcModeling" not in dk):
                raw_imgs = dv.get("images") or []
                for img in raw_imgs:
                    if isinstance(img, dict) and "__ref" in img:
                        img = apollo.get(img["__ref"], {})
                    if not isinstance(img, dict):
                        continue
                    orig = (img.get("origin") or img.get("url") or
                            img.get("originalUrl") or "")
                    if not orig:
                        continue
                    _add(orig, orig,
                         img.get("desc") or img.get("infoTitle") or "",
                         "brand", "", "", "",
                         str(img.get("width") or ""), str(img.get("height") or ""))

    # ── Media 타입 직접 수집 (fallback) ────────────────────────────────
    if not photos:
        for k, v in apollo.items():
            if k.startswith("Media:") and isinstance(v, dict):
                orig = v.get("url", "") or v.get("originalUrl", "")
                _add(orig, v.get("thumbnail", "") or orig,
                     v.get("title", ""), "media",
                     v.get("date", ""), v.get("link", ""),
                     v.get("authorname", "") or v.get("author", ""))
                if len(photos) >= max_count:
                    break

    return photos


def _parse_menus(apollo_menu: dict) -> list:
    menus = []
    seen  = set()

    def _add_menu(name, price_raw, desc, images, recommend):
        if not name or name in seen:
            return
        seen.add(name)
        price_str = price_raw if isinstance(price_raw, str) else str(price_raw or "")
        price_num = re.sub(r"[^\d]", "", price_str)
        imgs_clean = []
        for img in (images or []):
            if isinstance(img, dict):
                u = img.get("url") or img.get("thumbnail") or ""
                if u:
                    imgs_clean.append(_img_clean(u))
            elif isinstance(img, str) and img:
                imgs_clean.append(_img_clean(img))
        menus.append({
            "name":        name,
            "price":       f"{int(price_num):,}원" if price_num else "",
            "priceRaw":    price_str,
            "description": desc or "",
            "images":      imgs_clean,
            "recommend":   bool(recommend),
        })

    # Menu 타입
    for k, v in apollo_menu.items():
        if k.startswith("Menu:") and isinstance(v, dict):
            _add_menu(v.get("name", ""), v.get("price", ""),
                      v.get("description") or v.get("desc") or "",
                      v.get("images") or [],
                      v.get("recommend", False) or bool(v.get("isTop")))

    # 배민 메뉴
    if not menus:
        for k, v in apollo_menu.items():
            if k.startswith("PlaceDetail_BaeminMenu:") and isinstance(v, dict):
                _add_menu(v.get("name", ""), v.get("price", ""),
                          v.get("description", ""), v.get("images") or [], False)

    # fallback
    if not menus:
        pd = _place_detail(apollo_menu)
        menu_key = next((k for k in pd if k.startswith("menus")), None)
        if menu_key:
            for item in (pd.get(menu_key) or []):
                if isinstance(item, dict) and "__ref" in item:
                    item = apollo_menu.get(item["__ref"], {})
                if not isinstance(item, dict):
                    continue
                _add_menu(item.get("name", ""), item.get("price", ""),
                          item.get("description", ""), [],
                          item.get("recommend", False))
    return menus


# ─────────────────────────────────────────────
# GraphQL 호출 함수
# ─────────────────────────────────────────────

_GQL_BLOG_QUERY = """
query fsasReviews($input: FsasReviewsInput) {
  fsasReviews(input: $input) {
    total
    maxItemCount
    items {
      rank
      reviewId
      type
      typeName
      url
      home
      title
      contents
      authorName
      date
      createdString
      thumbnailUrl
      thumbnailUrlList
      thumbnailCount
      profileImageUrl
    }
  }
}
"""


_GQL_VISITOR_QUERY = """
query visitorReviews($input: VisitorReviewsInput) {
  visitorReviews(input: $input) {
    total
    items {
      id
      cursor
      reviewId
      rating
      body
      visited
      created
      thumbnail
      originType
      nickname
      tags { label }
      item { name }
    }
  }
}
"""


async def _gql_fetch_visitor_reviews(
    client: httpx.AsyncClient,
    business_id: str,
    business_type: str,
    size: int = 20,
    is_photo_used: bool = False,
) -> list:
    """GraphQL visitorReviews 호출 → 아이템 목록 반환"""
    payload = {
        "query": _GQL_VISITOR_QUERY,
        "variables": {
            "input": {
                "businessId": business_id,
                "businessType": business_type,
                "getReactions": False,
                "getTrailer": False,
                "includeContent": True,
                "includeReceiptPhotos": True,
                "isPhotoUsed": is_photo_used,
                "item": "0",
                "size": size,
            }
        },
    }
    try:
        r = await client.post(_GQL_ENDPOINT, json=payload, headers=_GQL_HEADERS)
        if r.status_code == 200:
            data = r.json()
            return (data.get("data", {}).get("visitorReviews", {}) or {}).get("items", [])
    except Exception:
        pass
    return []


async def _gql_fetch_blog_page(
    client: httpx.AsyncClient,
    business_id: str,
    business_type: str,
    page: int,
    display: int = 10,
    exclude_gdids: list | None = None,
) -> dict:
    """GraphQL fsasReviews 단일 페이지 호출"""
    payload = {
        "query": _GQL_BLOG_QUERY,
        "variables": {
            "input": {
                "businessId": business_id,
                "businessType": business_type,
                "buyWithMyMoneyType": False,
                "deviceType": "mobile",
                "display": display,
                "excludeGdids": exclude_gdids or [],
                "page": page,
                "query": None,
            }
        },
    }
    try:
        r = await client.post(_GQL_ENDPOINT, json=payload, headers=_GQL_HEADERS)
        if r.status_code == 200:
            data = r.json()
            return data.get("data", {}).get("fsasReviews", {}) or {}
    except Exception:
        pass
    return {}


# ─────────────────────────────────────────────
# 블로그 원문 크롤링 (선택적)
# ─────────────────────────────────────────────

async def _fetch_blog_full(client: httpx.AsyncClient, url: str) -> dict:
    try:
        r = await client.get(url)
        html = r.text
    except Exception:
        return {"full_text": "", "full_images": []}

    images = []
    for pat in [
        r'"originalUrl"\s*:\s*"([^"]+(?:blogfiles|postfiles)[^"]+)"',
        r'src="(https?://(?:blogfiles|postfiles)[^"?]+)"',
        r'"url"\s*:\s*"(https?://[^"]+(?:blogfiles|postfiles)[^"]+)"',
    ]:
        for u in re.findall(pat, html):
            clean = _img_clean(u)
            if clean and clean not in images:
                images.append(clean)

    text = ""
    for pat in [
        r'<div[^>]+class="[^"]*se-text-paragraph[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]+class="[^"]*se-main-container[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]+id="postViewArea"[^>]*>(.*?)</div>',
    ]:
        found = re.findall(pat, html, re.DOTALL)
        if found:
            parts = [re.sub(r"<[^>]+>", "", p).strip() for p in found]
            text = " ".join(p for p in parts if p)[:3000]
            break

    return {"full_text": text, "full_images": images[:20]}


# ─────────────────────────────────────────────
# 메인 파서 (비동기)
# ─────────────────────────────────────────────

async def parse_place_async(
    place_id: str,
    category: str = "restaurant",
    delay: float = 0.0,
    fetch_blog_content: bool = False,
    max_visitor_reviews: int = 100,
    max_blog_reviews: int = 100,
    max_photos: int = 200,
) -> dict:
    """
    네이버 플레이스 전체 정보 비동기 파싱

    Args:
        place_id: 네이버 플레이스 ID
        category: 업종 (restaurant/cafe/hairshop/accommodation/hospital/nailshop/place)
        delay: 최초 딜레이 (초)
        fetch_blog_content: True 시 블로그 원문+이미지 단계적 크롤링
        max_visitor_reviews: 최대 영수증 리뷰 수집 수 (기본 100)
        max_blog_reviews: 최대 블로그 리뷰 수집 수 (기본 100)
        max_photos: 최대 사진 수집 수 (기본 200)
    """
    result = {
        "mid": place_id,
        "url": f"https://m.place.naver.com/{category}/{place_id}",
        "name": "", "category": "", "roadAddress": "", "address": "",
        "phone": "", "x": "", "y": "",
        "keyword_list": [], "themes": [], "introduction": "",
        "visitor_review_count": 0, "blog_review_total": 0,
        "visitor_reviews": [], "blog_reviews": [],
        "menus": [],
        "business_hours": {},
        "conveniences": [],
        "photos": [],
        "static_map_url": "",
        "error": None,
    }

    if delay > 0:
        await asyncio.sleep(delay)

    try:
        fetch_menu = category not in _NO_MENU_CATEGORIES
        base_tabs = ["home", "review", "ugc", "info", "photo"]
        if fetch_menu:
            base_tabs.append("menu")

        base_urls = [_tab_url(place_id, category, t) for t in base_tabs]

        async with httpx.AsyncClient(
            headers=_HEADERS,
            follow_redirects=True,
            timeout=30.0,
        ) as client:

            # ── 1차: 기본 탭 모두 병렬 fetch ─────────────────────────
            base_resps = await asyncio.gather(
                *[client.get(u) for u in base_urls],
                return_exceptions=True,
            )

            raw_html = {}
            apollo   = {}
            for tab, resp in zip(base_tabs, base_resps):
                if isinstance(resp, Exception):
                    raw_html[tab] = ""
                    apollo[tab]   = {}
                else:
                    raw_html[tab] = resp.text
                    apollo[tab]   = _extract_apollo(resp.text)

            ap_home   = apollo.get("home", {})
            ap_review = apollo.get("review", {})
            ap_ugc    = apollo.get("ugc", {})
            ap_info   = apollo.get("info", {})
            ap_photo  = apollo.get("photo", {})
            ap_menu   = apollo.get("menu", {}) if fetch_menu else {}

            # ── 기본정보 ──────────────────────────────────────────────
            base_info = _parse_base(ap_home, place_id)
            result.update(base_info)
            if not result["name"]:
                # 홈 탭 미로드 시 info 탭 fallback
                base_info = _parse_base(ap_info, place_id)
                result.update({k: v for k, v in base_info.items() if v})

            result["keyword_list"]   = _parse_keyword_list(raw_html.get("home", ""))
            result["themes"]         = _parse_themes(ap_home)
            result["introduction"]   = _parse_description(ap_home)
            result["static_map_url"] = _parse_static_map_url(ap_home)

            # ── 리뷰 수 ──────────────────────────────────────────────
            counts = _parse_review_counts(ap_home, ap_review, ap_ugc, place_id)
            result["visitor_review_count"] = counts["visitor_review_count"]
            result["blog_review_total"]    = counts["blog_review_total"]
            blog_max_item                  = counts["_blog_max_item_count"]
            blog_gql_params                = counts["_blog_gql_params"]

            # ── 영수증 리뷰 (Apollo SSR + GraphQL 병렬 수집) ─────────
            seen_visitor_ids: set = set()

            # 1) Apollo SSR에서 첫 배치 (여러 visitorReviews 키 합산)
            visitor_reviews, _ = _parse_visitor_page(
                ap_review, seen_visitor_ids, max_visitor_reviews
            )

            # 2) GraphQL로 다양한 파라미터로 추가 수집
            #    (cursor 기반 페이지네이션은 미지원 → 파라미터 변형으로 보완)
            if len(visitor_reviews) < max_visitor_reviews:
                gql_tasks = [
                    # size=20, isPhotoUsed=False (일반 최신순)
                    _gql_fetch_visitor_reviews(
                        client, place_id, category, size=20, is_photo_used=False
                    ),
                    # size=20, isPhotoUsed=True (사진 있는 리뷰)
                    _gql_fetch_visitor_reviews(
                        client, place_id, category, size=20, is_photo_used=True
                    ),
                ]
                gql_results = await asyncio.gather(*gql_tasks, return_exceptions=True)

                for gql_items in gql_results:
                    if isinstance(gql_items, Exception) or not gql_items:
                        continue
                    for item in gql_items:
                        if len(visitor_reviews) >= max_visitor_reviews:
                            break
                        rid = item.get("id") or item.get("reviewId") or ""
                        if not rid or rid in seen_visitor_ids:
                            continue
                        seen_visitor_ids.add(rid)

                        # 이미지
                        images = []
                        thumb = item.get("thumbnail")
                        if thumb and isinstance(thumb, str):
                            images.append(_img_clean(thumb))

                        # 태그
                        tags = []
                        for t in (item.get("tags") or []):
                            if isinstance(t, dict):
                                label = t.get("label") or t.get("text") or ""
                                if label:
                                    tags.append(label)

                        item_obj = item.get("item") or {}
                        item_name = item_obj.get("name", "") if isinstance(item_obj, dict) else ""

                        visitor_reviews.append({
                            "id":         rid,
                            "rating":     item.get("rating", 0),
                            "body":       item.get("body", ""),
                            "originType": item.get("originType", ""),
                            "item":       item_name,
                            "author":     item.get("nickname", ""),
                            "visited":    item.get("visited", ""),
                            "created":    item.get("created", ""),
                            "viewCount":  0,
                            "images":     images,
                            "tags":       tags,
                            "cursor":     item.get("cursor", ""),
                        })

            result["visitor_reviews"] = visitor_reviews[:max_visitor_reviews]

            # ── 블로그 리뷰 (GraphQL page 페이지네이션) ──────────────
            seen_blog_ids: set = set()

            # 먼저 Apollo SSR에서 첫 페이지 수집
            blog_reviews = _parse_blog_page(ap_ugc, seen_blog_ids, max_blog_reviews)

            # GraphQL로 추가 페이지 수집
            if blog_gql_params and len(blog_reviews) < max_blog_reviews:
                business_id_param   = blog_gql_params.get("businessId", place_id)
                business_type_param = blog_gql_params.get("businessType", category)
                exclude_gdids       = blog_gql_params.get("excludeGdids", [])

                # 필요한 총 페이지 수 계산
                target_count = min(max_blog_reviews, blog_max_item or max_blog_reviews)
                total_needed = target_count - len(blog_reviews)
                pages_needed = (total_needed + 9) // 10  # 10개씩
                pages_needed = min(pages_needed, 50)  # 최대 50페이지

                if pages_needed > 0:
                    # 병렬로 GraphQL 호출 (5개씩 묶음)
                    gql_page_start = 1  # page=0은 SSR에서 이미 수집
                    while (
                        len(blog_reviews) < target_count
                        and gql_page_start <= pages_needed
                    ):
                        batch_end = min(gql_page_start + 4, pages_needed + 1)
                        gql_tasks = [
                            _gql_fetch_blog_page(
                                client,
                                business_id_param,
                                business_type_param,
                                p,
                                display=10,
                                exclude_gdids=exclude_gdids,
                            )
                            for p in range(gql_page_start, batch_end)
                        ]
                        gql_results = await asyncio.gather(*gql_tasks, return_exceptions=True)

                        for gql_res in gql_results:
                            if isinstance(gql_res, Exception) or not gql_res:
                                continue
                            items_raw = gql_res.get("items") or []
                            if not items_raw:
                                break
                            for item in items_raw:
                                if len(blog_reviews) >= max_blog_reviews:
                                    break
                                if not isinstance(item, dict):
                                    continue
                                rid = str(item.get("reviewId", "")) or str(item.get("rank", ""))
                                if rid in seen_blog_ids:
                                    continue
                                seen_blog_ids.add(rid)

                                raw_list = item.get("thumbnailUrlList") or []
                                if not raw_list and item.get("thumbnailUrl"):
                                    raw_list = [item["thumbnailUrl"]]
                                thumbnails = [_img_clean(u) for u in raw_list if u]

                                blog_reviews.append({
                                    "type":            item.get("type", ""),
                                    "typeName":        item.get("typeName", ""),
                                    "url":             item.get("url", ""),
                                    "home":            item.get("home", ""),
                                    "title":           item.get("title", ""),
                                    "contents":        item.get("contents", ""),
                                    "authorName":      item.get("authorName", ""),
                                    "date":            item.get("date", ""),
                                    "createdString":   item.get("createdString", ""),
                                    "reviewId":        item.get("reviewId", ""),
                                    "thumbnails":      thumbnails,
                                    "thumbnailCount":  item.get("thumbnailCount", 0),
                                    "profileImageUrl": item.get("profileImageUrl", ""),
                                    "rank":            item.get("rank"),
                                })

                        gql_page_start = batch_end

            # ── 블로그 원문 크롤링 (선택적) ───────────────────────────
            if fetch_blog_content and blog_reviews:
                blog_urls = [br["url"] for br in blog_reviews if br.get("url")]
                async with httpx.AsyncClient(
                    headers=_HEADERS, follow_redirects=True, timeout=15.0
                ) as c2:
                    blog_fulls = await asyncio.gather(
                        *[_fetch_blog_full(c2, u) for u in blog_urls],
                        return_exceptions=True,
                    )
                for br, full in zip(blog_reviews, blog_fulls):
                    if isinstance(full, Exception):
                        br["full_text"]   = ""
                        br["full_images"] = []
                    else:
                        br.update(full)

            result["blog_reviews"] = sorted(
                blog_reviews, key=lambda r: r.get("rank") or 9999
            )[:max_blog_reviews]

            # ── 영업시간 ──────────────────────────────────────────────
            result["business_hours"] = _parse_business_hours(ap_info)

            # ── 편의시설 ──────────────────────────────────────────────
            result["conveniences"] = _parse_conveniences(ap_info, place_id)

            # ── 사진 (다중 소스) ─────────────────────────────────────
            seen_photo_urls: set = set()
            photos = _parse_photos_from_apollo(ap_photo, seen_photo_urls, max_photos)
            # 부족하면 home 탭에서 추가
            if len(photos) < max_photos:
                extra = _parse_photos_from_apollo(
                    ap_home, seen_photo_urls, max_photos - len(photos)
                )
                photos.extend(extra)
            result["photos"] = photos

            # ── 메뉴 ─────────────────────────────────────────────────
            if fetch_menu:
                result["menus"] = _parse_menus(ap_menu)

            result["url"] = f"https://m.place.naver.com/{category}/{place_id}"

    except Exception as e:
        import traceback
        result["error"] = f"{e}\n{traceback.format_exc()[:800]}"

    return result


# ─────────────────────────────────────────────
# 동기 래퍼
# ─────────────────────────────────────────────

def parse_place(
    place_id: str,
    category: str = "restaurant",
    delay: float = 0.0,
    fetch_blog_content: bool = False,
    max_visitor_reviews: int = 100,
    max_blog_reviews: int = 100,
    max_photos: int = 200,
) -> dict:
    """동기 버전 (FastAPI/Jupyter 환경 호환)"""
    coro = parse_place_async(
        place_id, category, delay, fetch_blog_content,
        max_visitor_reviews, max_blog_reviews, max_photos,
    )
    try:
        loop = asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result(timeout=180)
    except RuntimeError:
        return asyncio.run(coro)


# ─────────────────────────────────────────────
# 결과 출력 헬퍼
# ─────────────────────────────────────────────

def _print_result(result: dict, elapsed: float = 0.0) -> None:
    print(f"\n{'='*60}")
    print(f"이름     : {result.get('name')}")
    print(f"카테고리 : {result.get('category')}")
    print(f"주소     : {result.get('roadAddress') or result.get('address')}")
    print(f"전화     : {result.get('phone')}")
    print(f"좌표     : ({result.get('x')}, {result.get('y')})")
    print(f"키워드   : {result.get('keyword_list')}")
    print(f"테마     : {result.get('themes')}")
    intro = result.get("introduction", "")
    print(f"소개글   : {intro[:100]}..." if len(intro) > 100 else f"소개글   : {intro}")

    vr = result.get("visitor_reviews", [])
    br = result.get("blog_reviews", [])
    vr_imgs = sum(len(r.get("images", [])) for r in vr)
    print(f"\n영수증리뷰: {result.get('visitor_review_count'):,}건 / 수집 {len(vr)}건 / 이미지 {vr_imgs}장")
    print(f"블로그리뷰: {result.get('blog_review_total'):,}건 / 수집 {len(br)}건")
    for b in br[:3]:
        print(f"  [{b.get('rank')}] {b.get('title', '')[:50]} (썸네일:{len(b.get('thumbnails', []))})")

    bh = result.get("business_hours", {})
    if bh:
        print(f"\n영업상태 : {bh.get('status')} — {bh.get('description')}")
        for d in bh.get("days", []):
            brk = f" (브레이크 {d['break_start']}~{d['break_end']})" if d.get("break_start") else ""
            lo  = f" (라스트오더 {d['last_order']})" if d.get("last_order") else ""
            clo = " [휴무]" if d.get("closed") else ""
            print(f"  {d['day']}: {d['open']}~{d['close']}{brk}{lo}{clo}")
        if bh.get("regular_closed"):
            print(f"  정기휴무: {bh['regular_closed']}")

    conv = result.get("conveniences", [])
    if conv:
        print(f"\n편의시설 : {conv}")

    photos = result.get("photos", [])
    print(f"\n사진     : {len(photos)}장 수집")
    for p in photos[:3]:
        print(f"  [{p.get('rank')}] {p.get('title', '')[:40]} ({p.get('section')})")

    menus = result.get("menus", [])
    print(f"\n메뉴     : {len(menus)}개")
    for m in menus[:5]:
        rec = " ★" if m.get("recommend") else ""
        print(f"  {m['name']} {m['price']}{rec}")

    if elapsed:
        print(f"\n소요시간 : {elapsed:.1f}초")
    print(f"에러     : {result.get('error')}")
    print("=" * 60)


# ─────────────────────────────────────────────
# 직접 실행
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    TEST_CASES = [
        ("accommodation", "1256903599"),
        ("hairshop",      "1222688077"),
        ("hospital",      "1776009650"),
        ("nailshop",      "1427705465"),
        ("place",         "2004177207"),
        ("restaurant",    "31553215"),
    ]

    if len(sys.argv) >= 2:
        place_id = sys.argv[1]
        category = sys.argv[2] if len(sys.argv) > 2 else "restaurant"
        max_v = int(sys.argv[3]) if len(sys.argv) > 3 else 100
        max_b = int(sys.argv[4]) if len(sys.argv) > 4 else 100
        cases = [(category, place_id, max_v, max_b)]
    else:
        cases = [(cat, pid, 30, 30) for cat, pid in TEST_CASES]

    for item in cases:
        cat, pid = item[0], item[1]
        max_v = item[2] if len(item) > 2 else 30
        max_b = item[3] if len(item) > 3 else 30
        print(f"\n파싱 시작: {pid} ({cat})")
        t0 = time.time()
        r = parse_place(pid, cat, delay=0.0,
                        max_visitor_reviews=max_v,
                        max_blog_reviews=max_b,
                        max_photos=200)
        elapsed = time.time() - t0
        _print_result(r, elapsed)
