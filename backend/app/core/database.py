"""
SQLAlchemy 데이터베이스 엔진 및 세션 관리
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from typing import Generator

from app.core.config import settings

# 동기 엔진 (Alembic, 일반 동작용)
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,          # 연결 유효성 자동 체크
    pool_size=10,                # 커넥션 풀 크기
    max_overflow=20,             # 최대 초과 커넥션 수
    echo=settings.DEBUG,         # SQL 쿼리 로그 출력 (개발 환경)
)

# 세션 팩토리
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# 모든 모델의 기본 클래스
Base = declarative_base()


def get_db() -> Generator:
    """
    FastAPI 의존성 주입용 DB 세션 제공자
    요청 처리 후 자동으로 세션을 닫음

    Usage:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
