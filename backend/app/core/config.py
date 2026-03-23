"""
애플리케이션 설정 관리
pydantic-settings를 사용하여 환경변수를 타입 안전하게 관리
"""
import json
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # =====================
    # 데이터베이스
    # =====================
    DATABASE_URL: str = "postgresql://nplace:nplace1234@localhost:5432/nplace"

    # =====================
    # Redis
    # =====================
    REDIS_URL: str = "redis://localhost:6379"

    # =====================
    # JWT 보안
    # =====================
    SECRET_KEY: str = "dev-secret-key-change-in-production-minimum-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # =====================
    # CORS
    # =====================
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # =====================
    # 환경
    # =====================
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # =====================
    # 선택적 (Sprint 2+에서 사용)
    # =====================
    KAKAO_CLIENT_ID: str = ""
    KAKAO_CLIENT_SECRET: str = ""
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    KAKAOPAY_ADMIN_KEY: str = ""
    NAVERPAY_CLIENT_ID: str = ""
    NAVERPAY_CLIENT_SECRET: str = ""

    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-northeast-2"
    S3_BUCKET_NAME: str = "nplace-images"

    SLACK_WEBHOOK_URL: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str):
            """CORS_ORIGINS JSON 문자열 파싱"""
            if field_name == "CORS_ORIGINS":
                try:
                    return json.loads(raw_val)
                except Exception:
                    return [raw_val]
            return raw_val


# 싱글톤 설정 인스턴스
settings = Settings()
