"""
Alembic 환경 설정
"""
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Alembic Config 객체 (alembic.ini에서 값을 가져옴)
config = context.config

# 로깅 설정
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 모든 모델의 메타데이터를 임포트해야 autogenerate가 작동함
from app.core.database import Base
from app.models import *  # noqa: F401, F403 - 모든 모델 임포트

target_metadata = Base.metadata

# 환경변수에서 DATABASE_URL 가져오기
import os
from app.core.config import settings

def get_url():
    return settings.DATABASE_URL


def run_migrations_offline() -> None:
    """오프라인 모드 마이그레이션 (DB 연결 없이 SQL 생성)"""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """온라인 모드 마이그레이션 (실제 DB에 적용)"""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
