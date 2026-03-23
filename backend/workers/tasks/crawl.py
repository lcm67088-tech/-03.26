"""
workers/tasks/crawl.py
──────────────────────────────────────────────────────────────────────────────
Celery 크롤링 태스크 (Sprint 9: 실제 Playwright 크롤러 연동)

태스크 목록:
  run_rank_check      — 키워드 순위 체크 (단건)
  crawl_place_info    — 플레이스 기본 정보 수집 (신규 등록 시)

재시도 전략:
  - 최대 3회 자동 재시도 (지수 백오프: 60 → 120 → 240초)
  - BotDetectedError 발생 시 30분 후 재시도 (IP 쿨다운)
  - PlaceNotFoundError는 재시도 없이 즉시 실패 처리
──────────────────────────────────────────────────────────────────────────────
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════════
# Task 1: 키워드 순위 체크
# ════════════════════════════════════════════════════════════════════════════════

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="workers.tasks.crawl.run_rank_check",
    # 지수 백오프: 1회=60s, 2회=120s, 3회=240s
    retry_backoff=True,
    retry_backoff_max=300,
)
def run_rank_check(self, crawl_job_id: str):
    """
    단일 (키워드, 플레이스) 쌍의 순위를 체크한다.

    Flow:
        1. DB에서 CrawlJob 조회 → PlaceKeyword, Place 로드
        2. status → running
        3. Playwright 크롤러 실행 (check_single_keyword)
        4. KeywordRanking 저장
        5. status → done / failed

    Args:
        crawl_job_id: CrawlJob UUID 문자열

    Returns:
        {
          "rank": int | None,
          "case_type": str,
          "keyword": str,
          "status": str,
          "bot_blocked": bool,
        }
    """
    from sqlalchemy.orm import Session
    from app.core.database import SessionLocal
    from app.models.crawl_job import CrawlJob, CrawlJobStatus
    from app.models.keyword import KeywordRanking, PlaceKeyword, RankCaseType
    from app.models.place import Place
    from workers.crawler.rank_checker import (
        check_single_keyword,
        BotDetectedError,
    )

    db: Session = SessionLocal()
    job = None

    try:
        # ── 1. CrawlJob 조회 ────────────────────────────────────────────────
        job = db.query(CrawlJob).filter(CrawlJob.id == crawl_job_id).first()
        if not job:
            logger.warning("CrawlJob 없음: %s", crawl_job_id)
            return {"status": "skipped", "reason": "job not found"}

        # ── 2. status → running ─────────────────────────────────────────────
        job.status = CrawlJobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        # ── 3. 키워드 + 플레이스 조회 ───────────────────────────────────────
        keyword_obj = db.query(PlaceKeyword).filter(
            PlaceKeyword.id == job.keyword_id
        ).first()

        if not keyword_obj or not keyword_obj.is_active:
            job.status = CrawlJobStatus.DONE
            job.finished_at = datetime.now(timezone.utc)
            job.result = {"status": "skipped", "reason": "keyword inactive"}
            db.commit()
            return job.result

        place = db.query(Place).filter(Place.id == keyword_obj.place_id).first()
        if not place or not place.is_active:
            job.status = CrawlJobStatus.DONE
            job.finished_at = datetime.now(timezone.utc)
            job.result = {"status": "skipped", "reason": "place inactive"}
            db.commit()
            return job.result

        target_mid = place.naver_place_id
        keyword_text = keyword_obj.keyword

        logger.info(
            "순위 체크 시작: keyword=%s mid=%s job=%s",
            keyword_text, target_mid, crawl_job_id
        )

        # ── 4. 실제 크롤링 ──────────────────────────────────────────────────
        try:
            rank_result = asyncio.run(
                check_single_keyword(
                    keyword=keyword_text,
                    target_mid=target_mid,
                    max_rank=5,
                )
            )
        except BotDetectedError as bot_err:
            # 봇 탐지: 30분 후 재시도
            logger.warning("봇 탐지 차단: %s — 30분 후 재시도", keyword_text)
            if job:
                job.status = CrawlJobStatus.QUEUED
                job.retry_count = (job.retry_count or 0) + 1
                db.commit()
            db.close()
            raise self.retry(exc=bot_err, countdown=1800)  # 30분

        # ── 5. 순위 결과 처리 ───────────────────────────────────────────────
        rank = rank_result.get("rank")          # int | None
        section_exists = rank_result.get("section_exists", False)
        is_top = rank_result.get("is_top_section", False)
        cpc_count = rank_result.get("cpc_count", 0)
        total_places = rank_result.get("total_places", 0)

        # case_type 결정
        if rank is None:
            case_type = RankCaseType.NOT_RANKED
        elif rank <= 3:
            case_type = RankCaseType.POPULAR
        else:
            case_type = RankCaseType.NORMAL

        # ── 6. KeywordRanking 저장 ──────────────────────────────────────────
        ranking = KeywordRanking(
            id=uuid.uuid4(),
            keyword_id=keyword_obj.id,
            rank=rank,
            case_type=case_type,
            crawled_at=datetime.now(timezone.utc),
            extra_data={
                "source":         "playwright",
                "job_id":         crawl_job_id,
                "section_exists": section_exists,
                "is_top_section": is_top,
                "cpc_count":      cpc_count,
                "total_places":   total_places,
                "status":         rank_result.get("status", ""),
                "bot_blocked":    rank_result.get("bot_blocked", False),
            },
        )
        db.add(ranking)

        # ── 7. CrawlJob → done ──────────────────────────────────────────────
        result_payload = {
            "rank":           rank,
            "case_type":      case_type.value,
            "keyword":        keyword_text,
            "status":         rank_result.get("status", ""),
            "section_exists": section_exists,
            "is_top_section": is_top,
            "cpc_count":      cpc_count,
            "total_places":   total_places,
            "bot_blocked":    rank_result.get("bot_blocked", False),
        }
        job.status = CrawlJobStatus.DONE
        job.finished_at = datetime.now(timezone.utc)
        job.result = result_payload
        db.commit()

        logger.info(
            "순위 체크 완료: keyword=%s rank=%s status=%s",
            keyword_text, rank, rank_result.get("status")
        )
        return result_payload

    except Exception as exc:
        # ── 실패 처리 & 재시도 ──────────────────────────────────────────────
        logger.error("run_rank_check 오류 [%s]: %s", crawl_job_id, exc)
        if job is not None:
            job.retry_count = (job.retry_count or 0) + 1
            if job.retry_count >= 3:
                job.status = CrawlJobStatus.FAILED
                job.finished_at = datetime.now(timezone.utc)
                job.result = {"error": str(exc)}
            else:
                job.status = CrawlJobStatus.QUEUED
            db.commit()

        db.close()
        raise self.retry(exc=exc)

    finally:
        db.close()


# ════════════════════════════════════════════════════════════════════════════════
# Task 2: 플레이스 기본 정보 수집
# ════════════════════════════════════════════════════════════════════════════════

@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    name="workers.tasks.crawl.crawl_place_info",
    retry_backoff=True,
    retry_backoff_max=300,
)
def crawl_place_info(self, place_id_str: str):
    """
    플레이스 기본 정보를 수집해 DB Place 레코드에 반영한다.

    플레이스 등록 직후, 또는 주기적 갱신 시 호출된다.

    Args:
        place_id_str: DB Place 테이블의 UUID 문자열

    Returns:
        {
          "place_id": str (naver_place_id),
          "name": str,
          "crawl_success": bool,
          "error": str | None,
        }
    """
    from sqlalchemy.orm import Session
    from app.core.database import SessionLocal
    from app.models.place import Place
    from workers.crawler.place_info import (
        fetch_place_info,
        apply_place_info_to_model,
        PlaceNotFoundError,
        PlaceInfoError,
    )

    db: Session = SessionLocal()

    try:
        # ── Place 레코드 조회 ────────────────────────────────────────────────
        place = db.query(Place).filter(Place.id == place_id_str).first()
        if not place:
            logger.warning("Place 없음: %s", place_id_str)
            return {"status": "skipped", "reason": "place not found"}

        naver_id = place.naver_place_id
        logger.info("플레이스 정보 수집 시작: db_id=%s naver_id=%s", place_id_str, naver_id)

        # ── 크롤링 실행 ──────────────────────────────────────────────────────
        try:
            info = asyncio.run(fetch_place_info(naver_id))
        except PlaceNotFoundError as e:
            # 존재하지 않는 플레이스 → 재시도 없이 즉시 실패
            logger.error("플레이스 없음 (재시도 안함): naver_id=%s — %s", naver_id, e)
            place.is_active = False
            db.commit()
            return {"place_id": naver_id, "crawl_success": False, "error": str(e)}

        except PlaceInfoError as e:
            # 수집 실패 → 재시도
            logger.warning("플레이스 수집 실패 (재시도 예정): %s — %s", naver_id, e)
            db.close()
            raise self.retry(exc=e)

        # ── DB 반영 ──────────────────────────────────────────────────────────
        apply_place_info_to_model(place, info)
        db.commit()

        logger.info(
            "플레이스 정보 수집 완료: naver_id=%s name=%s review=%d",
            naver_id, info.get("name"), info.get("review_count", 0)
        )

        return {
            "place_id":      naver_id,
            "name":          info.get("name", ""),
            "crawl_success": True,
            "error":         None,
        }

    except Exception as exc:
        logger.error("crawl_place_info 오류 [%s]: %s", place_id_str, exc)
        db.close()
        raise self.retry(exc=exc)

    finally:
        db.close()
