"""
장소(Place) 라우터 (Sprint 3 완성)

GET    /api/v1/places                  장소 목록 (워크스페이스별)
POST   /api/v1/places                  장소 등록
GET    /api/v1/places/dashboard-summary 대시보드 요약
GET    /api/v1/places/{place_id}        장소 상세
PUT    /api/v1/places/{place_id}        장소 수정 (alias, is_active)
DELETE /api/v1/places/{place_id}        장소 소프트 삭제
"""
import uuid
from datetime import datetime, date, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.core.constants import get_plan_limits
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.crawl_job import CrawlJob, CrawlJobStatus  # Sprint 4 신규
from app.models.keyword import KeywordRanking, PlaceKeyword
from app.models.order import Order, OrderStatus, PaymentStatus, Payment
from app.models.place import Place
from app.models.user import User, UserRole
from app.models.workspace import MemberRole, Workspace, WorkspaceMember
from app.schemas.place import (
    DashboardSummary,
    KeywordSummary,
    PlaceCreate,
    PlaceDetail,
    PlaceListItem,
    PlaceListResponse,
    PlaceRankSummary,
    PlaceUpdate,
    RankSummaryKeyword,
    RecentOrderItem,
)
from app.utils.naver import extract_naver_place_id, build_naver_place_url

router = APIRouter()


# ============================
# 권한 헬퍼
# ============================

def _verify_workspace_member(
    workspace_id: str,
    user: User,
    db: Session,
    required_roles: Optional[list[MemberRole]] = None,
) -> tuple[Workspace, WorkspaceMember]:
    """
    워크스페이스 멤버십 검증.

    Args:
        workspace_id: 대상 워크스페이스 UUID 문자열
        user: 현재 로그인 유저
        db: DB 세션
        required_roles: 필요한 역할 목록 (None이면 모든 역할 허용)

    Returns:
        (Workspace, WorkspaceMember) 튜플

    Raises:
        HTTPException 404: 워크스페이스 없음
        HTTPException 403: 멤버십 없거나 권한 부족
    """
    workspace = db.query(Workspace).filter(
        Workspace.id == workspace_id,
        Workspace.is_active == True,
    ).first()

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다",
        )

    # 어드민은 모든 워크스페이스 접근 가능
    if user.role in (UserRole.ADMIN, UserRole.SUPERADMIN):
        mock_member = WorkspaceMember()
        mock_member.role = MemberRole.OWNER
        return workspace, mock_member

    member = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user.id,
    ).first()

    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 워크스페이스에 접근 권한이 없습니다",
        )

    # 역할 체크
    if required_roles and member.role not in required_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이 작업을 수행할 권한이 없습니다",
        )

    return workspace, member


def _verify_place_member(
    place_id: str,
    user: User,
    db: Session,
    required_roles: Optional[list[MemberRole]] = None,
) -> tuple[Place, WorkspaceMember]:
    """
    장소에 대한 워크스페이스 멤버십 검증.

    Returns:
        (Place, WorkspaceMember) 튜플
    """
    place = db.query(Place).filter(
        Place.id == place_id,
        Place.is_active == True,
    ).first()

    if not place:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="장소를 찾을 수 없습니다",
        )

    _, member = _verify_workspace_member(
        str(place.workspace_id), user, db, required_roles
    )
    return place, member


# ============================
# 키워드 순위 헬퍼
# ============================

def _get_latest_ranking(keyword_id, db: Session) -> Optional[KeywordRanking]:
    """특정 키워드의 가장 최신 순위 레코드 반환"""
    return (
        db.query(KeywordRanking)
        .filter(KeywordRanking.keyword_id == keyword_id)
        .order_by(KeywordRanking.crawled_at.desc())
        .first()
    )


def _get_yesterday_ranking(keyword_id, db: Session) -> Optional[KeywordRanking]:
    """어제 순위 레코드 반환 (rank_change 계산용)"""
    from datetime import timedelta
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


def _build_keyword_summary(kw: PlaceKeyword, db: Session) -> KeywordSummary:
    """PlaceKeyword → KeywordSummary 변환 (최신 순위 + 변동 포함)"""
    latest = _get_latest_ranking(kw.id, db)
    yesterday = _get_yesterday_ranking(kw.id, db)

    latest_rank = latest.rank if latest else None
    case_type = latest.case_type.value if latest else None

    # rank_change 계산 (어제 순위 - 오늘 순위 = 양수면 상승)
    rank_change: Optional[int] = None
    if latest_rank is not None and yesterday and yesterday.rank is not None:
        rank_change = yesterday.rank - latest_rank  # 양수 = 순위 상승 (숫자 낮을수록 좋음)

    return KeywordSummary(
        id=str(kw.id),
        keyword=kw.keyword,
        is_primary=kw.is_primary,
        is_active=kw.is_active,
        group_name=kw.group_name,
        latest_rank=latest_rank,
        case_type=case_type,
        rank_change=rank_change,
    )


# ============================
# 장소 목록
# ============================

@router.get("", response_model=PlaceListResponse)
async def list_places(
    workspace_id: str = Query(..., description="워크스페이스 UUID"),
    skip: int = Query(0, ge=0, description="스킵 수"),
    limit: int = Query(20, ge=1, le=100, description="반환 수"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    워크스페이스의 활성 장소 목록 반환.

    - 워크스페이스 멤버십 검증
    - 키워드 수 + 키워드별 최신 순위 포함
    """
    _verify_workspace_member(workspace_id, current_user, db)

    # 활성 장소 조회
    query = db.query(Place).filter(
        Place.workspace_id == workspace_id,
        Place.is_active == True,
    )
    total = query.count()
    places = query.order_by(Place.created_at.desc()).offset(skip).limit(limit).all()

    items: list[PlaceListItem] = []
    for place in places:
        # 활성 키워드 목록
        active_keywords = [kw for kw in place.keywords if kw.is_active]
        keyword_count = len(active_keywords)

        # 키워드별 최신 순위
        latest_rankings = [_build_keyword_summary(kw, db) for kw in active_keywords]

        items.append(
            PlaceListItem(
                id=str(place.id),
                naver_place_id=place.naver_place_id,
                naver_place_url=place.naver_place_url,
                name=place.name,
                alias=place.alias,
                category=place.category,
                is_active=place.is_active,
                keyword_count=keyword_count,
                latest_rankings=latest_rankings,
                created_at=place.created_at,
            )
        )

    return PlaceListResponse(total=total, items=items)


# ============================
# 대시보드 요약 (장소 목록보다 먼저 등록 — FastAPI 경로 충돌 방지)
# ============================

@router.get("/dashboard-summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    workspace_id: str = Query(..., description="워크스페이스 UUID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    대시보드용 워크스페이스 요약 데이터.

    - 전체 장소 수 / 키워드 수
    - 이번달 주문 수 / 매출
    - 전체 키워드 평균 순위
    - 장소별 순위 요약 (최대 5개)
    - 최근 주문 5개
    """
    _verify_workspace_member(workspace_id, current_user, db)

    # 이번달 기간
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 1. 전체 장소 수
    total_places = db.query(func.count(Place.id)).filter(
        Place.workspace_id == workspace_id,
        Place.is_active == True,
    ).scalar() or 0

    # 2. 전체 활성 키워드 수
    total_keywords = (
        db.query(func.count(PlaceKeyword.id))
        .join(Place, Place.id == PlaceKeyword.place_id)
        .filter(
            Place.workspace_id == workspace_id,
            Place.is_active == True,
            PlaceKeyword.is_active == True,
        )
        .scalar() or 0
    )

    # 3. 이번달 주문 수 / 매출
    month_orders_query = db.query(Order).filter(
        Order.workspace_id == workspace_id,
        Order.ordered_at >= month_start,
        Order.status.notin_([OrderStatus.CANCELLED, OrderStatus.REFUNDED]),
    )
    this_month_orders = month_orders_query.count()
    this_month_revenue = (
        db.query(func.coalesce(func.sum(Order.total_amount), 0))
        .filter(
            Order.workspace_id == workspace_id,
            Order.ordered_at >= month_start,
            Order.status == OrderStatus.COMPLETED,
        )
        .scalar() or 0
    )

    # 4. 전체 키워드 평균 순위 (최신 순위 기준)
    active_places = db.query(Place).filter(
        Place.workspace_id == workspace_id,
        Place.is_active == True,
    ).all()

    all_ranks: list[int] = []
    rank_summary_list: list[PlaceRankSummary] = []

    for place in active_places:
        active_kws = [kw for kw in place.keywords if kw.is_active]
        kw_summaries: list[RankSummaryKeyword] = []

        for kw in active_kws:
            latest = _get_latest_ranking(kw.id, db)
            yesterday = _get_yesterday_ranking(kw.id, db)

            latest_rank = latest.rank if latest else None
            case_type = latest.case_type.value if latest else None

            rank_change: Optional[int] = None
            if latest_rank is not None and yesterday and yesterday.rank is not None:
                rank_change = yesterday.rank - latest_rank

            if latest_rank is not None:
                all_ranks.append(latest_rank)

            kw_summaries.append(
                RankSummaryKeyword(
                    keyword=kw.keyword,
                    rank=latest_rank,
                    case_type=case_type,
                    rank_change=rank_change,
                )
            )

        rank_summary_list.append(
            PlaceRankSummary(
                place_id=str(place.id),
                place_name=place.name,
                alias=place.alias,
                keywords=kw_summaries,
            )
        )

    # 평균 순위 계산
    avg_rank: Optional[float] = None
    if all_ranks:
        avg_rank = round(sum(all_ranks) / len(all_ranks), 1)

    # 5. 최근 주문 5개
    recent_orders_db = (
        db.query(Order)
        .filter(Order.workspace_id == workspace_id)
        .order_by(Order.created_at.desc())
        .limit(5)
        .all()
    )

    recent_orders = [
        RecentOrderItem(
            id=str(o.id),
            product_name=o.product_name,
            status=o.status.value,
            total_amount=o.total_amount,
            ordered_at=o.ordered_at,
        )
        for o in recent_orders_db
    ]

    return DashboardSummary(
        total_places=total_places,
        total_keywords=total_keywords,
        this_month_orders=this_month_orders,
        this_month_revenue=this_month_revenue,
        avg_rank=avg_rank,
        rank_summary=rank_summary_list,
        recent_orders=recent_orders,
    )


# ============================
# 장소 등록
# ============================

@router.post("", response_model=PlaceDetail, status_code=status.HTTP_201_CREATED)
async def create_place(
    data: PlaceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    장소 등록.

    1. 워크스페이스 멤버십 검증 (owner/manager만 가능)
    2. 플랜별 장소 수 한도 체크
    3. URL에서 naver_place_id 추출
    4. 같은 워크스페이스 내 중복 체크
    5. 장소 생성 (name은 naver_place_id 임시 사용, 크롤링은 Sprint 4)
    """
    workspace, _ = _verify_workspace_member(
        data.workspace_id,
        current_user,
        db,
        required_roles=[MemberRole.OWNER, MemberRole.MANAGER],
    )

    # 플랜별 한도 체크
    limits = get_plan_limits(workspace.plan.value)
    current_count = db.query(func.count(Place.id)).filter(
        Place.workspace_id == data.workspace_id,
        Place.is_active == True,
    ).scalar() or 0

    if current_count >= limits["max_places"]:
        plan_display = workspace.plan.value.capitalize()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"{plan_display} 플랜은 최대 {limits['max_places']}개 장소만 등록할 수 있습니다. "
                "업그레이드해주세요."
            ),
        )

    # naver_place_id 추출
    place_id_str = extract_naver_place_id(data.naver_place_url)
    if not place_id_str:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="올바른 네이버 플레이스 URL을 입력해주세요",
        )

    # 표준 URL 생성
    normalized_url = build_naver_place_url(place_id_str)

    # 중복 체크 (같은 워크스페이스 내 동일 place_id)
    existing = db.query(Place).filter(
        Place.workspace_id == data.workspace_id,
        Place.naver_place_id == place_id_str,
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 등록된 장소입니다",
        )

    # 장소 생성 (name은 alias 없으면 place_id로 임시 저장)
    temp_name = data.alias or f"플레이스 {place_id_str}"
    new_place = Place(
        id=uuid.uuid4(),
        workspace_id=uuid.UUID(data.workspace_id),
        naver_place_id=place_id_str,
        naver_place_url=normalized_url,
        name=temp_name,
        alias=data.alias,
        is_active=True,
    )
    db.add(new_place)
    db.commit()
    db.refresh(new_place)

    return PlaceDetail(
        id=str(new_place.id),
        naver_place_id=new_place.naver_place_id,
        naver_place_url=new_place.naver_place_url,
        name=new_place.name,
        alias=new_place.alias,
        category=new_place.category,
        address=new_place.address,
        is_active=new_place.is_active,
        keyword_count=0,
        keywords=[],
        recent_orders=[],
        created_at=new_place.created_at,
        updated_at=new_place.updated_at,
    )


# ============================
# 장소 상세
# ============================

@router.get("/{place_id}", response_model=PlaceDetail)
async def get_place(
    place_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    장소 상세 조회.

    - 워크스페이스 멤버십 검증
    - 활성 키워드 + 각 키워드별 최신 순위 포함
    - 해당 장소의 최근 주문 3개 포함
    """
    place, _ = _verify_place_member(place_id, current_user, db)

    # 활성 키워드 + 순위
    active_keywords = [kw for kw in place.keywords if kw.is_active]
    keyword_summaries = [_build_keyword_summary(kw, db) for kw in active_keywords]

    # 최근 주문 3개
    recent_orders_db = (
        db.query(Order)
        .filter(Order.place_id == place.id)
        .order_by(Order.created_at.desc())
        .limit(3)
        .all()
    )

    recent_orders = [
        {
            "id": str(o.id),
            "product_name": o.product_name,
            "status": o.status.value,
            "total_amount": o.total_amount,
            "ordered_at": o.ordered_at.isoformat() if o.ordered_at else None,
        }
        for o in recent_orders_db
    ]

    return PlaceDetail(
        id=str(place.id),
        naver_place_id=place.naver_place_id,
        naver_place_url=place.naver_place_url,
        name=place.name,
        alias=place.alias,
        category=place.category,
        address=place.address,
        is_active=place.is_active,
        keyword_count=len(active_keywords),
        keywords=keyword_summaries,
        recent_orders=recent_orders,
        created_at=place.created_at,
        updated_at=place.updated_at,
    )


# ============================
# 장소 수정
# ============================

@router.put("/{place_id}", response_model=PlaceDetail)
async def update_place(
    place_id: str,
    data: PlaceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    장소 수정 (alias, is_active만 변경 가능).

    - owner 또는 manager만 수정 가능
    """
    place, _ = _verify_place_member(
        place_id,
        current_user,
        db,
        required_roles=[MemberRole.OWNER, MemberRole.MANAGER],
    )

    # 수정 적용
    if data.alias is not None:
        place.alias = data.alias
    if data.is_active is not None:
        place.is_active = data.is_active

    db.commit()
    db.refresh(place)

    # 응답 구성 (get_place와 동일한 방식)
    active_keywords = [kw for kw in place.keywords if kw.is_active]
    keyword_summaries = [_build_keyword_summary(kw, db) for kw in active_keywords]

    recent_orders_db = (
        db.query(Order)
        .filter(Order.place_id == place.id)
        .order_by(Order.created_at.desc())
        .limit(3)
        .all()
    )
    recent_orders = [
        {
            "id": str(o.id),
            "product_name": o.product_name,
            "status": o.status.value,
            "total_amount": o.total_amount,
            "ordered_at": o.ordered_at.isoformat() if o.ordered_at else None,
        }
        for o in recent_orders_db
    ]

    return PlaceDetail(
        id=str(place.id),
        naver_place_id=place.naver_place_id,
        naver_place_url=place.naver_place_url,
        name=place.name,
        alias=place.alias,
        category=place.category,
        address=place.address,
        is_active=place.is_active,
        keyword_count=len(active_keywords),
        keywords=keyword_summaries,
        recent_orders=recent_orders,
        created_at=place.created_at,
        updated_at=place.updated_at,
    )


# ============================
# 장소 삭제 (소프트)
# ============================

@router.delete("/{place_id}")
async def delete_place(
    place_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    장소 소프트 삭제.

    - owner만 삭제 가능
    - is_active=False 처리 (실제 삭제 아님)
    - 연결된 활성 키워드도 모두 is_active=False 처리
    """
    place, _ = _verify_place_member(
        place_id,
        current_user,
        db,
        required_roles=[MemberRole.OWNER],
    )

    # 장소 비활성화
    place.is_active = False

    # 연결된 활성 키워드 모두 비활성화
    db.query(PlaceKeyword).filter(
        PlaceKeyword.place_id == place.id,
        PlaceKeyword.is_active == True,
    ).update({"is_active": False})

    db.commit()

    return {"message": "장소가 삭제되었습니다", "success": True}


# ============================
# 수동 크롤링 실행 (Sprint 4 신규)
# ============================

@router.post("/{place_id}/crawl-now")
async def crawl_now(
    place_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    특정 장소의 모든 활성 키워드에 대해 즉시 크롤링 실행.

    - owner/manager만 가능
    - 플랜별 일일 크롤링 횟수 한도 체크
      Redis Key: "crawl_count:{workspace_id}:{YYYY-MM-DD}"  TTL=오늘 자정까지
    - 한도 초과 시 429
    - 응답: { message, job_count }
    """
    place, _ = _verify_place_member(
        place_id,
        current_user,
        db,
        required_roles=[MemberRole.OWNER, MemberRole.MANAGER],
    )

    workspace = db.query(Workspace).filter(
        Workspace.id == place.workspace_id
    ).first()

    limits = get_plan_limits(workspace.plan.value)
    crawl_limit_per_day = limits["crawl_per_day"]

    # ── Redis 일일 크롤링 횟수 체크 ─────────────────────────
    try:
        from app.core.redis import get_redis

        redis_client = await get_redis()
        today_str = date.today().isoformat()
        redis_key = f"crawl_count:{place.workspace_id}:{today_str}"

        today_count = await redis_client.get(redis_key)
        today_count = int(today_count) if today_count else 0

        if today_count >= crawl_limit_per_day:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "오늘 크롤링 횟수를 모두 사용했습니다. "
                    "내일 다시 시도하거나 플랜을 업그레이드하세요."
                ),
            )

        # 카운터 증가 (TTL: 오늘 자정까지 남은 초)
        now = datetime.now(timezone.utc)
        midnight_utc = now.replace(hour=15, minute=0, second=0, microsecond=0)
        # KST 자정 = UTC 15:00
        if now >= midnight_utc:
            midnight_utc += timedelta(days=1)
        ttl_seconds = int((midnight_utc - now).total_seconds())

        await redis_client.setex(redis_key, ttl_seconds, today_count + 1)

    except HTTPException:
        raise
    except Exception:
        # Redis 연결 실패 시에도 크롤링은 허용 (가용성 우선)
        pass

    # ── 활성 키워드 목록 조회 ──────────────────────────────
    active_keywords = (
        db.query(PlaceKeyword)
        .filter(
            PlaceKeyword.place_id == place.id,
            PlaceKeyword.is_active == True,
        )
        .all()
    )

    if not active_keywords:
        return {"message": "등록된 활성 키워드가 없습니다", "job_count": 0}

    # ── 각 키워드별 크롤링 잡 생성 ────────────────────────
    job_ids: list[str] = []
    for kw in active_keywords:
        job = CrawlJob(
            id=uuid.uuid4(),
            keyword_id=kw.id,
            status=CrawlJobStatus.QUEUED,
            scheduled_at=datetime.now(timezone.utc),
            retry_count=0,
        )
        db.add(job)
        job_ids.append(str(job.id))

    db.commit()

    # ── Celery 태스크 적재 ─────────────────────────────────
    try:
        from workers.tasks.crawl import run_rank_check
        for job_id in job_ids:
            run_rank_check.delay(job_id)
    except ImportError:
        # Celery 없는 환경에서는 무시
        pass

    return {
        "message": f"크롤링을 시작했습니다 ({len(job_ids)}개 키워드)",
        "job_count": len(job_ids),
    }
