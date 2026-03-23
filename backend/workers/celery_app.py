"""
Celery 앱 설정 (Sprint 9 업데이트)

broker/backend: Redis
태스크 모듈: workers.tasks.crawl, workers.tasks.scheduler

Beat 스케줄 (KST 기준, UTC 변환):
  - 순위 체크: 매일 06:00, 10:00, 14:00, 20:00 (4회/일)
  - 플레이스 정보 갱신: 매일 03:00 (1회/일, 트래픽 적은 새벽)

큐 분리:
  - crawling  : 순위 체크 / 플레이스 수집 (CPU/네트워크 집약)
  - default   : 일반 태스크
"""
import os

from celery import Celery
from celery.schedules import crontab

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")

celery_app = Celery(
    "nplace",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "workers.tasks.crawl",
        "workers.tasks.scheduler",
    ],
)

celery_app.conf.update(
    # ── 직렬화 ───────────────────────────────────────────────────────────────
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # ── 타임존 ───────────────────────────────────────────────────────────────
    timezone="Asia/Seoul",
    enable_utc=True,

    # ── 결과 만료 (24시간) ────────────────────────────────────────────────────
    result_expires=86400,

    # ── 신뢰성 ───────────────────────────────────────────────────────────────
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # ── 큐 라우팅 ─────────────────────────────────────────────────────────────
    # Playwright 크롤러는 메모리를 많이 쓰므로 별도 큐로 분리
    task_routes={
        "workers.tasks.crawl.run_rank_check":   {"queue": "crawling"},
        "workers.tasks.crawl.crawl_place_info": {"queue": "crawling"},
        "workers.tasks.scheduler.*":            {"queue": "default"},
    },

    # ── 동시성 제한 ───────────────────────────────────────────────────────────
    # 크롤링 큐: 워커 1개당 Playwright 동시 실행 수 제한
    # (메모리 부족 방지. 서버 RAM에 따라 조정)
    worker_concurrency=int(os.environ.get("CRAWL_CONCURRENCY", "2")),

    # ── Beat 스케줄 ───────────────────────────────────────────────────────────
    beat_schedule={
        # ▶ 순위 체크 4회/일 (KST 06, 10, 14, 20시 → UTC 21, 01, 05, 11시)
        "rank-check-06h": {
            "task":     "workers.tasks.scheduler.daily_rank_check",
            "schedule": crontab(hour=21, minute=0),   # KST 06:00
            "options":  {"queue": "crawling"},
        },
        "rank-check-10h": {
            "task":     "workers.tasks.scheduler.daily_rank_check",
            "schedule": crontab(hour=1,  minute=0),   # KST 10:00
            "options":  {"queue": "crawling"},
        },
        "rank-check-14h": {
            "task":     "workers.tasks.scheduler.daily_rank_check",
            "schedule": crontab(hour=5,  minute=0),   # KST 14:00
            "options":  {"queue": "crawling"},
        },
        "rank-check-20h": {
            "task":     "workers.tasks.scheduler.daily_rank_check",
            "schedule": crontab(hour=11, minute=0),   # KST 20:00
            "options":  {"queue": "crawling"},
        },
        # ▶ 플레이스 기본 정보 갱신: KST 03:00 (= UTC 18:00 전날)
        "refresh-place-info": {
            "task":     "workers.tasks.scheduler.refresh_all_place_info",
            "schedule": crontab(hour=18, minute=0),   # KST 03:00
            "options":  {"queue": "crawling"},
        },
    },
)
