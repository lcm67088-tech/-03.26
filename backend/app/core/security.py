"""
JWT 토큰 발급 및 검증, 비밀번호 해시
"""
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# bcrypt 비밀번호 해시 컨텍스트
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============================
# 비밀번호 유틸리티
# ============================

def get_password_hash(password: str) -> str:
    """평문 비밀번호를 bcrypt 해시로 변환"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """평문 비밀번호와 bcrypt 해시 비교"""
    return pwd_context.verify(plain_password, hashed_password)


# ============================
# JWT 토큰 유틸리티
# ============================

def create_access_token(data: Dict[str, Any]) -> str:
    """
    JWT 액세스 토큰 생성 (만료: 60분)

    Args:
        data: 토큰에 담을 페이로드 (sub: user_id 필수)

    Returns:
        JWT 문자열
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({
        "exp": expire,
        "type": "access",
        "iat": datetime.utcnow(),
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    JWT 리프레시 토큰 생성 (만료: 30일)

    Args:
        data: 토큰에 담을 페이로드 (sub: user_id 필수)

    Returns:
        JWT 문자열
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "iat": datetime.utcnow(),
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """
    JWT 토큰 디코딩 및 검증

    Args:
        token: JWT 문자열

    Returns:
        디코딩된 페이로드 딕셔너리

    Raises:
        HTTPException 401: 토큰 만료
        HTTPException 401: 토큰 유효하지 않음
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload

    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰이 만료되었습니다",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다",
            headers={"WWW-Authenticate": "Bearer"},
        )


def decode_refresh_token(token: str) -> Dict[str, Any]:
    """
    리프레시 토큰 전용 디코딩 (type 검증 포함)

    Raises:
        HTTPException 401: 잘못된 토큰 타입
    """
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 리프레시 토큰입니다",
        )
    return payload


def get_user_id_from_token(token: str) -> str:
    """
    토큰에서 user_id(sub) 추출

    Raises:
        HTTPException 401: sub 없음
    """
    payload = decode_token(token)
    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다",
        )
    return user_id
