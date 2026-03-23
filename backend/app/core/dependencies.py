"""
FastAPI 의존성 주입 모듈 (Sprint 2 완성)
실제 DB 조회 + 권한 체크 포함
"""
from typing import Optional, Tuple
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User, UserRole
from app.models.workspace import Workspace, WorkspaceMember

# OAuth2 Bearer 토큰 스키마
# tokenUrl은 실제 로그인 엔드포인트 경로
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)


# ============================
# 현재 유저 의존성
# ============================

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    JWT 토큰 검증 후 현재 유저 반환

    Raises:
        HTTPException 401: 토큰 없음 / 유효하지 않음 / 만료
        HTTPException 401: 유저 없음
        HTTPException 403: 계정 비활성화
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증이 필요합니다",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    # 토큰 디코딩 (만료/유효하지 않으면 decode_token에서 예외 발생)
    payload = decode_token(token)

    # sub(user_id) 추출
    user_id: Optional[str] = payload.get("sub")
    token_type: Optional[str] = payload.get("type")

    if not user_id or token_type != "access":
        raise credentials_exception

    # DB에서 유저 조회
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유저를 찾을 수 없습니다",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 계정 활성화 여부 체크
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다. 고객센터에 문의해주세요",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    활성화된 유저만 반환 (get_current_user 래퍼)
    is_active 이중 체크
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다",
        )
    return current_user


# ============================
# 권한 의존성
# ============================

async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    어드민 권한 체크

    Raises:
        HTTPException 403: admin/superadmin 아닌 경우
    """
    if current_user.role not in (UserRole.ADMIN, UserRole.SUPERADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="어드민 권한이 필요합니다",
        )
    return current_user


async def require_superadmin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    슈퍼어드민 권한 체크

    Raises:
        HTTPException 403: superadmin 아닌 경우
    """
    if current_user.role != UserRole.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="슈퍼어드민 권한이 필요합니다",
        )
    return current_user


# ============================
# 워크스페이스 컨텍스트 의존성
# ============================

async def get_workspace_context(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Tuple[Workspace, WorkspaceMember]:
    """
    워크스페이스 접근 권한 체크

    Args:
        workspace_id: 접근할 워크스페이스 UUID

    Returns:
        (Workspace, WorkspaceMember) 튜플

    Raises:
        HTTPException 404: 워크스페이스 없음
        HTTPException 403: 멤버십 없음 (접근 불가)
    """
    # 워크스페이스 조회
    workspace = db.query(Workspace).filter(
        Workspace.id == workspace_id,
        Workspace.is_active == True,
    ).first()

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다",
        )

    # 멤버십 확인 (어드민은 모든 워크스페이스 접근 가능)
    if current_user.role in (UserRole.ADMIN, UserRole.SUPERADMIN):
        # 어드민은 owner 역할로 가상 멤버십 부여
        from app.models.workspace import MemberRole
        mock_member = WorkspaceMember()
        mock_member.workspace_id = workspace.id
        mock_member.user_id = current_user.id
        mock_member.role = MemberRole.OWNER
        return workspace, mock_member

    member = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == current_user.id,
    ).first()

    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 워크스페이스에 접근 권한이 없습니다",
        )

    return workspace, member


def get_user_first_workspace(
    current_user: User,
    db: Session,
) -> Optional[Workspace]:
    """
    유저의 첫 번째(주) 워크스페이스 반환
    (owner인 워크스페이스 우선, 없으면 member인 것)
    """
    # owner인 워크스페이스 우선
    workspace = db.query(Workspace).filter(
        Workspace.owner_id == current_user.id,
        Workspace.is_active == True,
    ).first()

    if not workspace:
        # member인 워크스페이스
        member = db.query(WorkspaceMember).filter(
            WorkspaceMember.user_id == current_user.id,
        ).first()
        if member:
            workspace = db.query(Workspace).filter(
                Workspace.id == member.workspace_id,
                Workspace.is_active == True,
            ).first()

    return workspace


# 하위 호환 alias
get_workspace = get_workspace_context
