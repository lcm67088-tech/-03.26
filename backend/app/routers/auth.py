"""
인증 라우터 - Sprint 2 완성 (7개 엔드포인트)

POST /api/v1/auth/register       회원가입
POST /api/v1/auth/login          로그인
POST /api/v1/auth/refresh        토큰 갱신
POST /api/v1/auth/logout         로그아웃
POST /api/v1/auth/forgot-password  비밀번호 찾기
POST /api/v1/auth/reset-password   비밀번호 재설정
GET  /api/v1/auth/me             현재 유저 정보
"""
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import redis.asyncio as aioredis

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.redis import (
    get_redis,
    increment_login_fail,
    get_login_fail_count,
    reset_login_fail,
    save_refresh_token,
    get_refresh_token,
    delete_refresh_token,
    save_pwd_reset_token,
    get_pwd_reset_user_id,
    delete_pwd_reset_token,
    save_email_verify_token,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_password_hash,
    verify_password,
)
from app.models.user import User, UserRole
from app.models.workspace import Workspace, WorkspaceMember, WorkspacePlan, MemberRole
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MeResponse,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    TokenResponse,
    UserInfo,
    WorkspaceInfo,
)

router = APIRouter()

# 로그인 최대 실패 횟수
MAX_LOGIN_ATTEMPTS = 5


# ============================
# 헬퍼 함수
# ============================

def _build_token_response(
    user: User,
    workspace: Workspace,
    access_token: str,
    refresh_token: str,
) -> TokenResponse:
    """TokenResponse 객체 생성 헬퍼"""
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserInfo(
            id=str(user.id),
            email=user.email,
            name=user.name,
            role=user.role.value,
            phone=user.phone,
            is_active=user.is_active,
            email_verified=user.email_verified,
        ),
        workspace=WorkspaceInfo(
            id=str(workspace.id),
            name=workspace.name,
            plan=workspace.plan.value,
        ),
    )


def _get_user_workspace(db: Session, user: User) -> Workspace:
    """유저의 주 워크스페이스 반환 (owner 우선)"""
    workspace = db.query(Workspace).filter(
        Workspace.owner_id == user.id,
        Workspace.is_active == True,
    ).first()

    if not workspace:
        # owner가 아닌 경우 member로 속한 첫 번째 워크스페이스
        member = db.query(WorkspaceMember).filter(
            WorkspaceMember.user_id == user.id,
        ).first()
        if member:
            workspace = db.query(Workspace).filter(
                Workspace.id == member.workspace_id,
                Workspace.is_active == True,
            ).first()

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="소속된 워크스페이스를 찾을 수 없습니다",
        )

    return workspace


# ============================
# 회원가입
# ============================

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest,
    db: Session = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    회원가입

    1. 이메일 중복 체크
    2. 비밀번호 해시 저장
    3. 기본 워크스페이스 자동 생성 (free 플랜)
    4. WorkspaceMember owner로 등록
    5. 이메일 인증 토큰 생성 (콘솔 mock 출력)
    """
    # 이메일 중복 체크
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 사용 중인 이메일입니다",
        )

    # 유저 생성
    new_user = User(
        id=uuid.uuid4(),
        email=data.email,
        hashed_password=get_password_hash(data.password),
        name=data.name,
        phone=data.phone,
        role=UserRole.USER,
        is_active=True,
        email_verified=False,
    )
    db.add(new_user)
    db.flush()  # ID 확보를 위해 flush (commit 전)

    # 기본 워크스페이스 생성
    default_workspace = Workspace(
        id=uuid.uuid4(),
        owner_id=new_user.id,
        name=f"{new_user.name}의 워크스페이스",
        plan=WorkspacePlan.FREE,
        is_active=True,
    )
    db.add(default_workspace)
    db.flush()

    # 워크스페이스 멤버십 (owner)
    membership = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=default_workspace.id,
        user_id=new_user.id,
        role=MemberRole.OWNER,
    )
    db.add(membership)

    # DB 커밋
    db.commit()
    db.refresh(new_user)
    db.refresh(default_workspace)

    # 이메일 인증 토큰 생성 및 Redis 저장
    verify_token = secrets.token_urlsafe(32)
    await save_email_verify_token(verify_token, str(new_user.id), redis)

    # 이메일 발송 Mock (콘솔 출력)
    print(
        f"\n[이메일 인증] {new_user.email} →"
        f" http://localhost:3000/verify-email?token={verify_token}\n"
    )

    return RegisterResponse(
        user=UserInfo(
            id=str(new_user.id),
            email=new_user.email,
            name=new_user.name,
            role=new_user.role.value,
            phone=new_user.phone,
            is_active=new_user.is_active,
            email_verified=new_user.email_verified,
        ),
        workspace=WorkspaceInfo(
            id=str(default_workspace.id),
            name=default_workspace.name,
            plan=default_workspace.plan.value,
        ),
        message="회원가입이 완료되었습니다. 이메일을 확인해주세요.",
    )


# ============================
# 로그인
# ============================

@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    로그인

    1. 로그인 잠금 체크 (5회 실패 시 15분 잠금)
    2. 이메일+비밀번호 검증
    3. 실패 횟수 추적 / 성공 시 초기화
    4. JWT access + refresh 토큰 발급
    5. refresh 토큰 Redis 저장
    """
    # 잠금 체크
    fail_count = await get_login_fail_count(data.email, redis)
    if fail_count >= MAX_LOGIN_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="로그인 시도 횟수를 초과했습니다. 15분 후 다시 시도해주세요.",
        )

    # 유저 조회
    user = db.query(User).filter(User.email == data.email).first()

    # 비밀번호 검증 (유저 없음 / 비밀번호 불일치 동일 응답 → 보안)
    if not user or not verify_password(data.password, user.hashed_password):
        # 실패 횟수 증가
        count = await increment_login_fail(data.email, redis)
        remaining = MAX_LOGIN_ATTEMPTS - count
        if remaining > 0:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"이메일 또는 비밀번호가 올바르지 않습니다. (남은 시도: {remaining}회)",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="로그인 시도 횟수를 초과했습니다. 15분 후 다시 시도해주세요.",
            )

    # 계정 활성화 체크
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다. 고객센터에 문의해주세요.",
        )

    # 로그인 성공 → 실패 카운터 초기화
    await reset_login_fail(data.email, redis)

    # 토큰 발급
    user_id_str = str(user.id)
    access_token = create_access_token({"sub": user_id_str})
    refresh_token = create_refresh_token({"sub": user_id_str})

    # Refresh 토큰 Redis 저장
    await save_refresh_token(user_id_str, refresh_token, redis)

    # 워크스페이스 조회
    workspace = _get_user_workspace(db, user)

    return _build_token_response(user, workspace, access_token, refresh_token)


# ============================
# 토큰 갱신
# ============================

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token_endpoint(
    data: RefreshRequest,
    db: Session = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    토큰 갱신 (Refresh Token Rotation)

    1. refresh_token 디코딩 및 검증
    2. Redis에 저장된 토큰과 대조 (재사용 방지)
    3. 새 access_token + refresh_token 발급
    4. Redis 갱신
    """
    # 리프레시 토큰 디코딩
    payload = decode_refresh_token(data.refresh_token)
    user_id: str = payload.get("sub", "")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다",
        )

    # Redis에 저장된 토큰과 비교 (토큰 재사용 방지)
    stored_token = await get_refresh_token(user_id, redis)
    if not stored_token or stored_token != data.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰이 만료되었거나 이미 사용된 토큰입니다",
        )

    # 유저 조회
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 유저입니다",
        )

    # 새 토큰 발급 (Rotation)
    new_access_token = create_access_token({"sub": user_id})
    new_refresh_token = create_refresh_token({"sub": user_id})

    # Redis 갱신
    await save_refresh_token(user_id, new_refresh_token, redis)

    # 워크스페이스 조회
    workspace = _get_user_workspace(db, user)

    return _build_token_response(user, workspace, new_access_token, new_refresh_token)


# ============================
# 로그아웃
# ============================

@router.post("/logout", response_model=MessageResponse)
async def logout(
    current_user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    로그아웃

    Redis에서 refresh_token 삭제
    (access_token은 만료될 때까지 유효 - 짧은 만료 시간으로 보완)
    """
    await delete_refresh_token(str(current_user.id), redis)
    return MessageResponse(message="로그아웃되었습니다", success=True)


# ============================
# 비밀번호 찾기
# ============================

@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    data: ForgotPasswordRequest,
    db: Session = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    비밀번호 찾기 (재설정 링크 발송)

    보안상 유저 존재 여부와 무관하게 동일한 응답 반환
    (이메일 열거 공격 방지)
    """
    user = db.query(User).filter(User.email == data.email).first()

    if user:
        # 재설정 토큰 생성
        reset_token = secrets.token_urlsafe(32)

        # Redis에 저장 (TTL 1시간)
        await save_pwd_reset_token(reset_token, str(user.id), redis)

        # 이메일 발송 Mock (콘솔 출력)
        print(
            f"\n[비밀번호 재설정] {data.email}"
            f" → http://localhost:3000/reset-password?token={reset_token}\n"
        )

    # 유저 존재 여부와 무관하게 동일 응답
    return MessageResponse(
        message="이메일을 발송했습니다. 받은편지함과 스팸함을 확인해주세요.",
        success=True,
    )


# ============================
# 비밀번호 재설정
# ============================

@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    비밀번호 재설정

    1. Redis에서 토큰 → user_id 조회
    2. 비밀번호 변경
    3. 토큰 삭제
    4. 기존 refresh_token 무효화 (강제 재로그인)
    """
    # Redis에서 토큰 검증
    user_id = await get_pwd_reset_user_id(data.token, redis)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않거나 만료된 재설정 링크입니다",
        )

    # 유저 조회
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="유저를 찾을 수 없습니다",
        )

    # 비밀번호 변경
    user.hashed_password = get_password_hash(data.new_password)
    db.commit()

    # 재설정 토큰 삭제
    await delete_pwd_reset_token(data.token, redis)

    # 기존 refresh 토큰 무효화 (강제 재로그인)
    await delete_refresh_token(user_id, redis)

    return MessageResponse(
        message="비밀번호가 변경되었습니다. 새 비밀번호로 로그인해주세요.",
        success=True,
    )


# ============================
# 현재 유저 정보 조회
# ============================

@router.get("/me", response_model=MeResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    현재 로그인 유저 정보 조회

    access_token에서 유저 정보 반환
    워크스페이스 정보 포함 (Sprint 3 대시보드에서 필요)
    """
    # 워크스페이스 조회 (없어도 에러 안 냄)
    workspace = db.query(Workspace).filter(
        Workspace.owner_id == current_user.id,
        Workspace.is_active == True,
    ).first()

    workspace_info = None
    if workspace:
        workspace_info = WorkspaceInfo(
            id=str(workspace.id),
            name=workspace.name,
            plan=workspace.plan.value,
        )

    return MeResponse(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        role=current_user.role.value,
        phone=current_user.phone,
        is_active=current_user.is_active,
        email_verified=current_user.email_verified,
        workspace=workspace_info,
    )
