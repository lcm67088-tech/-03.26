"""
스케줄러 Celery 태스크 (Sprint 9 업데이트)

daily_rank_check:
  - Celery Beat가 매일 KST 06:00 / 10:00 / 14:00 / 20:00 에 실행 (4회/일)
  - is_active=True 인 모든 PlaceKeyword 조회
  - 각 키워드별 CrawlJob 생성 → run_rank_check.delay(job_id)

refresh_all_place_info:
  - 매일 KST 03:00 에 실행 (1회/일)
  - 모든 활성 Place의 기본 정보(리뷰수, 영업시간 등)를 갱신
"""
import uuid
from datetime import datetime, timezone

from workers.celery_app import celery_app


@celery_app.task(name="workers.tasks.scheduler.daily_rank_check")
def daily_rank_check():
    """
    매일 KST 06:00 실행되는 전체 키워드 순위 체크 스케줄 태스크.

    Flow:
        1. 모든 활성 워크스페이스의 활성 장소의 활성 키워드 조회
        2. 각 키워드별 CrawlJob 레코드 생성
        3. run_rank_check.delay(job_id) 로 큐에 적재
        4. 처리 결과 로그 출력

    Returns:
        dict: { "total_keywords": n, "queued": n, "timestamp": ... }
    """
    from sqlalchemy.orm import Session
    from app.core.database import SessionLocal
    from app.models.crawl_job import CrawlJob, CrawlJobStatus
    from app.models.keyword import PlaceKeyword
    from app.models.place import Place
    from app.models.workspace import Workspace
    from workers.tasks.crawl import run_rank_check

    db: Session = SessionLocal()

    try:
        # ── 활성 키워드 전체 조회 ─────────────────────────────
        active_keywords = (
            db.query(PlaceKeyword)
            .join(Place, Place.id == PlaceKeyword.place_id)
            .join(Workspace, Workspace.id == Place.workspace_id)
            .filter(
                Workspace.is_active == True,
                Place.is_active == True,
                PlaceKeyword.is_active == True,
            )
            .all()
        )

        total = len(active_keywords)
        queued_count = 0
        now = datetime.now(timezone.utc)

        for kw in active_keywords:
            # ── CrawlJob 생성 ───────────────────────────────
            job = CrawlJob(
                id=uuid.uuid4(),
                keyword_id=kw.id,
                status=CrawlJobStatus.QUEUED,
                scheduled_at=now,
                retry_count=0,
            )
            db.add(job)
            db.flush()  # job.id 확정

            # ── Celery 태스크 적재 ──────────────────────────
            run_rank_check.delay(str(job.id))
            queued_count += 1

        db.commit()

        result = {
            "total_keywords": total,
            "queued": queued_count,
            "timestamp": now.isoformat(),
        }
        print(f"[daily_rank_check] 완료: {result}")
        return result

    except Exception as exc:
        db.rollback()
        print(f"[daily_rank_check] 오류 발생: {exc}")
        raise

    finally:
        db.close()


@celery_app.task(name="workers.tasks.scheduler.refresh_all_place_info")
def refresh_all_place_info():
    """
    매일 KST 03:00 실행 — 모든 활성 플레이스의 기본 정보 갱신.

    Flow:
        1. is_active=True 인 모든 Place 조회
        2. 각 Place별 crawl_place_info.delay(place_id) 큐에 적재

    Returns:
        {"total_places": n, "queued": n, "timestamp": ...}
    """
    from sqlalchemy.orm import Session
    from app.core.database import SessionLocal
    from app.models.place import Place
    from app.models.workspace import Workspace
    from workers.tasks.crawl import crawl_place_info

    db: Session = SessionLocal()
    try:
        active_places = (
            db.query(Place)
            .join(Workspace, Workspace.id == Place.workspace_id)
            .filter(
                Workspace.is_active == True,
                Place.is_active == True,
            )
            .all()
        )

        total = len(active_places)
        queued = 0
        now = datetime.now(timezone.utc)

        for place in active_places:
            crawl_place_info.apply_async(
                args=[str(place.id)],
                queue="crawling",
            )
            queued += 1

        result = {
            "total_places": total,
            "queued": queued,
            "timestamp": now.isoformat(),
        }
        print(f"[refresh_all_place_info] 완료: {result}")
        return result

    except Exception as exc:
        db.rollback()
        print(f"[refresh_all_place_info] 오류: {exc}")
        raise
    finally:
        db.close()
