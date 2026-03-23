"""
Workspace 모델
B2B 워크스페이스 및 멤버십 관리
Sprint 8: payment_method JSON 컬럼 추가
"""
import enum

from sqlalchemy import Boolean, Column, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB, JSON
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class WorkspacePlan(str, enum.Enum):
    """구독 플랜"""
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class MemberRole(str, enum.Enum):
    """워크스페이스 멤버 역할"""
    OWNER = "owner"
    MANAGER = "manager"
    VIEWER = "viewer"


class Workspace(BaseModel):
    """
    워크스페이스 테이블
    에이전시 또는 개인 사업자의 작업 공간
    
    Relations:
        - owner: 소유자 (User)
        - members: 멤버십 목록
        - places: 등록된 장소 목록
        - orders: 주문 목록
    """
    __tablename__ = "workspaces"
    __table_args__ = {"comment": "워크스페이스 (에이전시/사업자 단위)"}

    # 소유자
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="워크스페이스 소유자 (User FK)",
    )

    # 기본 정보
    name = Column(
        String(100),
        nullable=False,
        comment="워크스페이스 이름",
    )

    # 구독 플랜
    plan = Column(
        Enum(WorkspacePlan),
        default=WorkspacePlan.FREE,
        nullable=False,
        comment="구독 플랜 (free/starter/pro/enterprise)",
    )

    # 상태
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="워크스페이스 활성화 상태",
    )

    # 추가 데이터 (유연한 확장을 위한 JSONB)
    extra_data = Column(
        JSONB,
        nullable=True,
        default=dict,
        comment="추가 설정 및 메타데이터 (JSONB)",
    )

    # Sprint 8: 결제 수단 정보 (Mock PG용 카드 정보 저장)
    # 구조: {"card_number_last4": "1234", "card_brand": "Visa",
    #         "exp_month": "12", "exp_year": "27", "pg_customer_id": "cust_xxx"}
    payment_method = Column(
        JSON,
        nullable=True,
        comment="결제 수단 정보 (카드 last4, 브랜드, 유효기간 등 JSON)",
    )

    # Relations
    owner = relationship(
        "User",
        back_populates="owned_workspaces",
    )
    members = relationship(
        "WorkspaceMember",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    places = relationship(
        "Place",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    orders = relationship(
        "Order",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    # Sprint 8: 구독/결제 관계
    subscriptions = relationship(
        "Subscription",
        back_populates="workspace",
        cascade="all, delete-orphan",
        order_by="Subscription.created_at.desc()",
    )
    billing_histories = relationship(
        "BillingHistory",
        back_populates="workspace",
        cascade="all, delete-orphan",
        order_by="BillingHistory.created_at.desc()",
    )
    # Sprint 7: 알림 관계
    notifications = relationship(
        "Notification",
        back_populates="workspace",
        cascade="all, delete-orphan",
        lazy="dynamic",
        order_by="Notification.created_at.desc()",
    )

    def __repr__(self) -> str:
        return f"<Workspace {self.name} ({self.plan})>"


class WorkspaceMember(BaseModel):
    """
    워크스페이스 멤버십 테이블 (유저 ↔ 워크스페이스 M:N)
    """
    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_user"),
        {"comment": "워크스페이스 멤버십"},
    )

    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="워크스페이스 FK",
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="유저 FK",
    )
    role = Column(
        Enum(MemberRole),
        default=MemberRole.VIEWER,
        nullable=False,
        comment="멤버 역할 (owner/manager/viewer)",
    )

    # Relations
    workspace = relationship("Workspace", back_populates="members")
    user = relationship("User", back_populates="workspace_memberships")

    def __repr__(self) -> str:
        return f"<WorkspaceMember workspace={self.workspace_id} user={self.user_id} role={self.role}>"
