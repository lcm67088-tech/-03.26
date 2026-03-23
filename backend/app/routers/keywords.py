"""
키워드 라우터 (Sprint 4 완성)

모든 엔드포인트는 /api/v1/places/{place_id}/keywords 하위에 위치.
main.py에서 prefix="/api/v1" 로 등록됨.

GET    /places/{place_id}/keywords                        키워드 목록
POST   /places/{place_id}/keywords                        키워드 등록
PUT    /places/{place_id}/keywords/{keyword_id}           키워드 수정
DELETE /places/{place_id}/keywords/{keyword_id}           키워드 소프트 삭제
GET    /places/{place_id}/keywords/{keyword_id}/rankings  순위 이력
GET    /places/{place_id}/rankings/summary                장소 전체 순위 요약
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.constants import get_plan_limits
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.crawl_job import CrawlJob, CrawlJobStatus
from app.models.keyword import KeywordRanking, PlaceKeyword, RankCaseType
from app.models.place import Place
from app.models.user import User, UserRole
from app.models.workspace import MemberRole, Workspace, WorkspaceMember
from app.schemas.keyword import (
    KeywordCreate,
    KeywordListResponse,
    KeywordUpdate,
    KeywordWithRank,
    PlaceRankingSummaryKeyword,
    PlaceRankingSummaryResponse,
    RankingHistoryResponse,
    RankingPoint,
)

router = APIRouter()


# ============================
# 내부 헬퍼 — 멤버십 검증
# ============================

def _verify_workspace_member(
    workspace_id,
    user: User,
    db: Session,
    required_roles: Optional[List[MemberRole]] = None,
) -> tuple[Workspace, WorkspaceMember]:
    """워크스페이스 멤버십 검증 (places.py 와 동일 패턴)"""
    workspace = db.query(Workspace).filter(
        Workspace.id == workspace_id,
        Workspace.is_active == True,
    ).first()

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다",
        )

    # 어드민은 무조건 통과
    if user.role in (UserRole.ADMIN, UserRole.SUPERADMIN):
        mock = WorkspaceMember()
        mock.role = MemberRole.OWNER
        return workspace, mock

    member = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user.id,
    ).first()

    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 워크스페이스에 접근 권한이 없습니다",
        )

    if required_roles and member.role not in required_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이 작업을 수행할 권한이 없습니다",
        )

    return workspace, member


def _get_place_with_member(
    place_id: str,
    user: User,
    db: Session,
    required_roles: Optional[List[MemberRole]] = None,
) -> tuple[Place, WorkspaceMember]:
    """
    장소 조회 + 워크스페이스 멤버십 검증.
    삭제된 장소(is_active=False)도 조회할 수 있도록 필터를 걸지 않는다.
    """
    place = db.query(Place).filter(Place.id == place_id).first()
    if not place:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="장소를 찾을 수 없습니다",
        )
    _, member = _verify_workspace_member(
        place.workspace_id, user, db, required_roles
    )
    return place, member


# ============================
# 내부 헬퍼 — 순위 통계 계산
# ============================

def _get_latest_ranking(keyword_id, db: Session) -> Optional[KeywordRanking]:
    """최신 순위 레코드 반환"""
    return (
        db.query(KeywordRanking)
        .filter(KeywordRanking.keyword_id == keyword_id)
        .order_by(KeywordRanking.crawled_at.desc())
        .first()
    )


def _get_yesterday_ranking(keyword_id, db: Session) -> Optional[KeywordRanking]:
    """어제 순위 레코드 반환 (rank_change 계산용)"""
    yesterday_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=1)
    yesterday_end = yesterday_start + timedelta(days=1)

    return (
        db.query(KeywordRanking)
        .filter(
            KeywordRanking.keyword_id == keyword_id,
            KeywordRanking.crawled_at >= yesterday_start,
            KeywordRanking.crawled_at < yesterday_end,
        )
        .order_by(KeywordRanking.crawled_at.desc())
        .first()
    )


def _calc_7d_avg(keyword_id, db: Session) -> Optional[float]:
    """
    최근 7일 평균 순위 계산.
    미진입(rank=None)은 제외하고 평균 산출.
    """
    since = datetime.now(timezone.utc) - timedelta(days=7)
    ranks = (
        db.query(KeywordRanking.rank)
        .filter(
            KeywordRanking.keyword_id == keyword_id,
            KeywordRanking.crawled_at >= since,
            KeywordRanking.rank.isnot(None),
        )
        .all()
    )
    values = [r.rank for r in ranks if r.rank is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _calc_best_worst_rank(keyword_id, db: Session) -> tuple[Optional[int], Optional[int]]:
    """역대 최고(best) / 최저(worst) 순위 계산"""
    result = (
        db.query(
            func.min(KeywordRanking.rank).label("best"),
            func.max(KeywordRanking.rank).label("worst"),
        )
        .filter(
            KeywordRanking.keyword_id == keyword_id,
            KeywordRanking.rank.isnot(None),
        )
        .first()
    )
    if result:
        return result.best, result.worst
    return None, None


def _build_keyword_with_rank(kw: PlaceKeyword, db: Session) -> KeywordWithRank:
    """PlaceKeyword → KeywordWithRank 변환 (전체 통계 포함)"""
    latest = _get_latest_ranking(kw.id, db)
    yesterday = _get_yesterday_ranking(kw.id, db)
    avg_7d = _calc_7d_avg(kw.id, db)
    best, worst = _calc_best_worst_rank(kw.id, db)

    latest_rank = latest.rank if latest else None
    case_type = latest.case_type.value if latest else None
    crawled_at = latest.crawled_at if latest else None

    # rank_change: 어제 순위 - 오늘 순위 (양수=순위 상승)
    rank_change: Optional[int] = None
    if latest_rank is not None and yesterday and yesterday.rank is not None:
        rank_change = yesterday.rank - latest_rank

    return KeywordWithRank(
        id=str(kw.id),
        keyword=kw.keyword,
        is_primary=kw.is_primary,
        group_name=kw.group_name,
        is_active=kw.is_active,
        latest_rank=latest_rank,
        case_type=case_type,
        rank_change=rank_change,
        rank_7d_avg=avg_7d,
        best_rank=best,
        worst_rank=worst,
        crawled_at=crawled_at,
    )


def _create_crawl_job(keyword_id, db: Session) -> CrawlJob:
    """
    키워드에 대한 크롤링 잡 생성 및 DB 저장.
    Celery 태스크는 이 함수 외부에서 .delay() 호출.
    """
    job = CrawlJob(
        id=uuid.uuid4(),
        keyword_id=keyword_id,
        status=CrawlJobStatus.QUEUED,
        scheduled_at=datetime.now(timezone.utc),
        retry_count=0,
    )
    db.add(job)
    return job


# ============================
# 엔드포인트 1: 키워드 목록
# ============================

@router.get(
    "/places/{place_id}/keywords",
    response_model=KeywordListResponse,
)
async def list_keywords(
    place_id: str,
    include_inactive: bool = Query(False, description="비활성 키워드 포함 여부"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    장소의 키워드 목록 반환.

    - 기본적으로 is_active=True 키워드만 반환
    - include_inactive=true 이면 모든 키워드 반환
    - 각 키워드에 latest_rank, rank_change, case_type, 7d평균, 역대최고/최저 포함
    - 정렬: is_primary 먼저 → rank 오름차순 → keyword 이름 오름차순
    """
    _get_place_with_member(place_id, current_user, db)

    query = db.query(PlaceKeyword).filter(
        PlaceKeyword.place_id == place_id
    )
    if not include_inactive:
        query = query.filter(PlaceKeyword.is_active == True)

    keywords = query.all()

    items = [_build_keyword_with_rank(kw, db) for kw in keywords]

    # is_primary 먼저, 이후 rank 오름차순 (None은 맨 뒤)
    def sort_key(k: KeywordWithRank):
        rank_val = k.latest_rank if k.latest_rank is not None else 9999
        return (0 if k.is_primary else 1, rank_val, k.keyword)

    items.sort(key=sort_key)

    return KeywordListResponse(total=len(items), items=items)


# ============================
# 엔드포인트 2: 키워드 등록
# ============================

@router.post(
    "/places/{place_id}/keywords",
    response_model=KeywordWithRank,
    status_code=status.HTTP_201_CREATED,
)
async def create_keyword(
    place_id: str,
    data: KeywordCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    키워드 등록.

    1. owner/manager 권한 체크
    2. 워크스페이스 전체 키워드 수 한도 체크 (플랜 기준)
    3. 동일 장소 내 같은 키워드 중복 체크
    4. 키워드 생성
    5. 즉시 크롤링 잡 생성 + Celery 태스크 적재
    """
    place, _ = _get_place_with_member(
        place_id,
        current_user,
        db,
        required_roles=[MemberRole.OWNER, MemberRole.MANAGER],
    )

    # ── 워크스페이스 전체 키워드 수 한도 체크 ──────────────────
    workspace = db.query(Workspace).filter(
        Workspace.id == place.workspace_id
    ).first()

    limits = get_plan_limits(workspace.plan.value)

    # 워크스페이스 소속 모든 활성 장소의 활성 키워드 합산
    total_active_keywords = (
        db.query(func.count(PlaceKeyword.id))
        .join(Place, Place.id == PlaceKeyword.place_id)
        .filter(
            Place.workspace_id == place.workspace_id,
            Place.is_active == True,
            PlaceKeyword.is_active == True,
        )
        .scalar() or 0
    )

    if total_active_keywords >= limits["max_keywords"]:
        plan_display = workspace.plan.value.capitalize()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"{plan_display} 플랜은 장소당 최대 {limits['max_keywords']}개 "
                "키워드만 등록할 수 있습니다. 업그레이드해주세요."
            ),
        )

    # ── 동일 장소 내 중복 키워드 체크 ─────────────────────────
    existing = db.query(PlaceKeyword).filter(
        PlaceKeyword.place_id == place_id,
        PlaceKeyword.keyword == data.keyword,
        PlaceKeyword.is_active == True,
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 등록된 키워드입니다",
        )

    # ── 키워드 생성 ─────────────────────────────────────────
    new_kw = PlaceKeyword(
        id=uuid.uuid4(),
        place_id=uuid.UUID(place_id),
        keyword=data.keyword,
        is_primary=data.is_primary,
        group_name=data.group_name,
        is_active=True,
    )
    db.add(new_kw)
    db.flush()  # ID 확정 (crawl_job FK 참조 위해 필요)

    # ── 즉시 크롤링 잡 생성 ─────────────────────────────────
    job = _create_crawl_job(new_kw.id, db)
    db.commit()
    db.refresh(new_kw)

    # ── Celery 태스크 적재 (import 지연 → 순환 참조 방지) ────────
    try:
        from workers.tasks.crawl import run_rank_check
        run_rank_check.delay(str(job.id))
    except ImportError:
        # Celery 워커가 없는 환경(테스트 등)에서는 무시
        pass

    return _build_keyword_with_rank(new_kw, db)


# ============================
# 엔드포인트 3: 키워드 수정
# ============================

@router.put(
    "/places/{place_id}/keywords/{keyword_id}",
    response_model=KeywordWithRank,
)
async def update_keyword(
    place_id: str,
    keyword_id: str,
    data: KeywordUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    키워드 수정 (is_primary, group_name, is_active 변경 가능).
    owner/manager만 가능.
    """
    _get_place_with_member(
        place_id,
        current_user,
        db,
        required_roles=[MemberRole.OWNER, MemberRole.MANAGER],
    )

    keyword = db.query(PlaceKeyword).filter(
        PlaceKeyword.id == keyword_id,
        PlaceKeyword.place_id == place_id,
    ).first()

    if not keyword:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="키워드를 찾을 수 없습니다",
        )

    # 변경 적용
    if data.is_primary is not None:
        keyword.is_primary = data.is_primary
    if data.group_name is not None:
        keyword.group_name = data.group_name
    if data.is_active is not None:
        keyword.is_active = data.is_active

    db.commit()
    db.refresh(keyword)

    return _build_keyword_with_rank(keyword, db)


# ============================
# 엔드포인트 4: 키워드 소프트 삭제
# ============================

@router.delete(
    "/places/{place_id}/keywords/{keyword_id}",
)
async def delete_keyword(
    place_id: str,
    keyword_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    키워드 소프트 삭제 (is_active=False).
    owner/manager만 가능.
    """
    _get_place_with_member(
        place_id,
        current_user,
        db,
        required_roles=[MemberRole.OWNER, MemberRole.MANAGER],
    )

    keyword = db.query(PlaceKeyword).filter(
        PlaceKeyword.id == keyword_id,
        PlaceKeyword.place_id == place_id,
        PlaceKeyword.is_active == True,
    ).first()

    if not keyword:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="키워드를 찾을 수 없습니다",
        )

    keyword.is_active = False
    db.commit()

    return {"message": "키워드가 삭제되었습니다", "success": True}


# ============================
# 엔드포인트 5: 순위 이력
# ============================

@router.get(
    "/places/{place_id}/keywords/{keyword_id}/rankings",
    response_model=RankingHistoryResponse,
)
async def get_keyword_rankings(
    place_id: str,
    keyword_id: str,
    period: str = Query("30d", regex="^(7d|30d|90d)$", description="기간 (7d|30d|90d)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    특정 키워드의 순위 이력 반환.

    period 기준:
    - 7d  : 최근 7일 각 날짜별 최신 1개 (최대 7포인트)
    - 30d : 최근 30일 각 날짜별 최신 1개 (최대 30포인트)
    - 90d : 최근 90일 주별 평균 (최대 13포인트)
    """
    _get_place_with_member(place_id, current_user, db)

    keyword = db.query(PlaceKeyword).filter(
        PlaceKeyword.id == keyword_id,
        PlaceKeyword.place_id == place_id,
    ).first()

    if not keyword:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="키워드를 찾을 수 없습니다",
        )

    now = datetime.now(timezone.utc)

    # ── period 별 처리 ─────────────────────────────────────
    if period in ("7d", "30d"):
        days = 7 if period == "7d" else 30
        since = now - timedelta(days=days)

        # 날짜별 최신 1개 레코드 추출
        # 서브쿼리: 날짜별 최대 crawled_at
        rankings_raw = (
            db.query(KeywordRanking)
            .filter(
                KeywordRanking.keyword_id == keyword_id,
                KeywordRanking.crawled_at >= since,
            )
            .order_by(KeywordRanking.crawled_at.asc())
            .all()
        )

        # 날짜별로 가장 최근 것 1개씩 선택
        date_map: dict = {}
        for r in rankings_raw:
            date_key = r.crawled_at.date()
            # 최신 기록으로 덮어쓰기
            date_map[date_key] = r

        # 날짜 오름차순 정렬
        sorted_dates = sorted(date_map.keys())
        ranking_points = [
            RankingPoint(
                rank=date_map[d].rank,
                case_type=date_map[d].case_type.value,
                crawled_at=date_map[d].crawled_at,
            )
            for d in sorted_dates
        ]

    else:
        # 90d: 주별 평균
        since = now - timedelta(days=90)
        rankings_raw = (
            db.query(KeywordRanking)
            .filter(
                KeywordRanking.keyword_id == keyword_id,
                KeywordRanking.crawled_at >= since,
                KeywordRanking.rank.isnot(None),
            )
            .order_by(KeywordRanking.crawled_at.asc())
            .all()
        )

        # ISO 주 단위로 그룹핑
        week_map: dict = {}
        for r in rankings_raw:
            # ISO 주 번호 (year, week)
            iso = r.crawled_at.isocalendar()
            week_key = (iso[0], iso[1])
            if week_key not in week_map:
                week_map[week_key] = {"ranks": [], "crawled_at": r.crawled_at}
            week_map[week_key]["ranks"].append(r.rank)

        sorted_weeks = sorted(week_map.keys())
        ranking_points = []
        for wk in sorted_weeks:
            ranks = week_map[wk]["ranks"]
            avg = round(sum(ranks) / len(ranks)) if ranks else None
            ranking_points.append(
                RankingPoint(
                    rank=avg,
                    case_type="normal",          # 주간 평균이므로 normal 로 통일
                    crawled_at=week_map[wk]["crawled_at"],
                )
            )

    return RankingHistoryResponse(
        keyword_id=str(keyword.id),
        keyword=keyword.keyword,
        period=period,
        rankings=ranking_points,
    )


# ============================
# 엔드포인트 6: 장소 전체 순위 요약
# ============================

@router.get(
    "/places/{place_id}/rankings/summary",
    response_model=PlaceRankingSummaryResponse,
)
async def get_place_rankings_summary(
    place_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    장소 전체 키워드의 최신 순위 요약.

    - 모든 활성 키워드에 대해:
      latest_rank, case_type, crawled_at, rank_change,
      rank_7d_avg, best_rank, worst_rank 포함
    - is_primary 먼저, 이후 rank 오름차순 정렬
    """
    place, _ = _get_place_with_member(place_id, current_user, db)

    active_keywords = (
        db.query(PlaceKeyword)
        .filter(
            PlaceKeyword.place_id == place_id,
            PlaceKeyword.is_active == True,
        )
        .all()
    )

    result_keywords: list[PlaceRankingSummaryKeyword] = []
    for kw in active_keywords:
        latest = _get_latest_ranking(kw.id, db)
        yesterday = _get_yesterday_ranking(kw.id, db)
        avg_7d = _calc_7d_avg(kw.id, db)
        best, worst = _calc_best_worst_rank(kw.id, db)

        latest_rank = latest.rank if latest else None
        case_type = latest.case_type.value if latest else None
        crawled_at = latest.crawled_at if latest else None

        rank_change: Optional[int] = None
        if latest_rank is not None and yesterday and yesterday.rank is not None:
            rank_change = yesterday.rank - latest_rank

        result_keywords.append(
            PlaceRankingSummaryKeyword(
                id=str(kw.id),
                keyword=kw.keyword,
                is_primary=kw.is_primary,
                group_name=kw.group_name,
                latest_rank=latest_rank,
                case_type=case_type,
                crawled_at=crawled_at,
                rank_change=rank_change,
                rank_7d_avg=avg_7d,
                best_rank=best,
                worst_rank=worst,
            )
        )

    # is_primary 먼저, rank 오름차순
    result_keywords.sort(
        key=lambda k: (0 if k.is_primary else 1, k.latest_rank or 9999, k.keyword)
    )

    return PlaceRankingSummaryResponse(
        place_id=str(place.id),
        place_name=place.alias or place.name,
        keywords=result_keywords,
    )
