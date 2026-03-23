"""
User 모델
플랫폼 사용자 계정 관리
"""
import enum

from sqlalchemy import Boolean, Column, Enum, String
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class UserRole(str, enum.Enum):
    """유저 역할"""
    USER = "user"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


class User(BaseModel):
    """
    플랫폼 유저 테이블
    
    Relations:
        - workspaces: 소유한 워크스페이스 목록
        - workspace_memberships: 소속된 워크스페이스 멤버십
    """
    __tablename__ = "users"
    __table_args__ = {"comment": "플랫폼 유저 계정"}

    # 기본 정보
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="이메일 (로그인 ID)",
    )
    hashed_password = Column(
        String(255),
        nullable=False,
        comment="bcrypt 해시 비밀번호",
    )
    name = Column(
        String(100),
        nullable=False,
        comment="이름",
    )
    phone = Column(
        String(20),
        nullable=True,
        comment="전화번호",
    )

    # 역할 및 상태
    role = Column(
        Enum(UserRole),
        default=UserRole.USER,
        nullable=False,
        comment="유저 역할 (user/admin/superadmin)",
    )
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="계정 활성화 상태",
    )
    email_verified = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="이메일 인증 여부",
    )

    # Relations
    owned_workspaces = relationship(
        "Workspace",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    workspace_memberships = relationship(
        "WorkspaceMember",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    # Sprint 7: 알림 관계
    notifications = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic",
        order_by="Notification.created_at.desc()",
    )
    notification_settings = relationship(
        "NotificationSetting",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"
