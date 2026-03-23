"""
Redis 비동기 클라이언트 모듈
redis.asyncio 사용 (edge runtime 호환)

사용처:
- 로그인 실패 횟수 추적 (login_fail:{email})
- Refresh 토큰 저장 (refresh:{user_id})
- 비밀번호 재설정 토큰 (pwd_reset:{token})
- 이메일 인증 토큰 (email_verify:{token})
"""
from typing import Optional
import redis.asyncio as aioredis
from app.core.config import settings

# 전역 Redis 클라이언트 (싱글톤)
_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    """
    Redis 클라이언트 싱글톤 반환
    FastAPI 의존성 주입용
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
    return _redis_client


async def close_redis() -> None:
    """애플리케이션 종료 시 Redis 연결 닫기"""
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None


# ============================
# Redis Key 상수
# ============================
class RedisKeys:
    """Redis 키 상수 정의 (일관성 유지)"""

    @staticmethod
    def login_fail(email: str) -> str:
        """로그인 실패 카운터 키"""
        return f"login_fail:{email}"

    @staticmethod
    def refresh_token(user_id: str) -> str:
        """Refresh 토큰 저장 키"""
        return f"refresh:{user_id}"

    @staticmethod
    def pwd_reset(token: str) -> str:
        """비밀번호 재설정 토큰 키"""
        return f"pwd_reset:{token}"

    @staticmethod
    def email_verify(token: str) -> str:
        """이메일 인증 토큰 키"""
        return f"email_verify:{token}"


# ============================
# TTL 상수 (초 단위)
# ============================
class RedisTTL:
    LOGIN_FAIL_LOCKOUT = 900        # 15분 (로그인 잠금)
    REFRESH_TOKEN = 60 * 60 * 24 * 30  # 30일
    PWD_RESET_TOKEN = 3600          # 1시간
    EMAIL_VERIFY_TOKEN = 86400      # 24시간


# ============================
# Redis 헬퍼 함수
# ============================

async def increment_login_fail(email: str, redis: aioredis.Redis) -> int:
    """
    로그인 실패 횟수 증가
    처음 실패 시 TTL 15분 설정
    Returns: 현재 실패 횟수
    """
    key = RedisKeys.login_fail(email)
    count = await redis.incr(key)
    if count == 1:
        # 첫 실패 시에만 TTL 설정
        await redis.expire(key, RedisTTL.LOGIN_FAIL_LOCKOUT)
    return count


async def get_login_fail_count(email: str, redis: aioredis.Redis) -> int:
    """로그인 실패 횟수 조회"""
    key = RedisKeys.login_fail(email)
    val = await redis.get(key)
    return int(val) if val else 0


async def reset_login_fail(email: str, redis: aioredis.Redis) -> None:
    """로그인 성공 시 실패 카운터 초기화"""
    await redis.delete(RedisKeys.login_fail(email))


async def save_refresh_token(user_id: str, token: str, redis: aioredis.Redis) -> None:
    """Refresh 토큰 Redis 저장 (TTL 30일)"""
    await redis.setex(
        RedisKeys.refresh_token(user_id),
        RedisTTL.REFRESH_TOKEN,
        token,
    )


async def get_refresh_token(user_id: str, redis: aioredis.Redis) -> Optional[str]:
    """Redis에서 Refresh 토큰 조회"""
    return await redis.get(RedisKeys.refresh_token(user_id))


async def delete_refresh_token(user_id: str, redis: aioredis.Redis) -> None:
    """Refresh 토큰 삭제 (로그아웃)"""
    await redis.delete(RedisKeys.refresh_token(user_id))


async def save_pwd_reset_token(token: str, user_id: str, redis: aioredis.Redis) -> None:
    """비밀번호 재설정 토큰 저장 (TTL 1시간)"""
    await redis.setex(
        RedisKeys.pwd_reset(token),
        RedisTTL.PWD_RESET_TOKEN,
        user_id,
    )


async def get_pwd_reset_user_id(token: str, redis: aioredis.Redis) -> Optional[str]:
    """비밀번호 재설정 토큰으로 user_id 조회"""
    return await redis.get(RedisKeys.pwd_reset(token))


async def delete_pwd_reset_token(token: str, redis: aioredis.Redis) -> None:
    """비밀번호 재설정 토큰 삭제"""
    await redis.delete(RedisKeys.pwd_reset(token))


async def save_email_verify_token(token: str, user_id: str, redis: aioredis.Redis) -> None:
    """이메일 인증 토큰 저장 (TTL 24시간)"""
    await redis.setex(
        RedisKeys.email_verify(token),
        RedisTTL.EMAIL_VERIFY_TOKEN,
        user_id,
    )


async def get_email_verify_user_id(token: str, redis: aioredis.Redis) -> Optional[str]:
    """이메일 인증 토큰으로 user_id 조회"""
    return await redis.get(RedisKeys.email_verify(token))


async def delete_email_verify_token(token: str, redis: aioredis.Redis) -> None:
    """이메일 인증 토큰 삭제"""
    await redis.delete(RedisKeys.email_verify(token))

# 하위 호환 동기 클라이언트 (미사용 시 None)
redis_client = None
