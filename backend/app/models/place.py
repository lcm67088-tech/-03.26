"""
Place 모델
네이버 플레이스 업체 정보 관리
"""
from sqlalchemy import Boolean, Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Place(BaseModel):
    """
    네이버 플레이스 업체 테이블
    
    Relations:
        - workspace: 소속 워크스페이스
        - keywords: 등록된 키워드 목록
        - orders: 주문 목록
    """
    __tablename__ = "places"
    __table_args__ = {"comment": "네이버 플레이스 업체 정보"}

    # 소속 워크스페이스
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="워크스페이스 FK",
    )

    # 네이버 플레이스 정보
    naver_place_id = Column(
        String(100),
        nullable=False,
        index=True,
        comment="네이버 플레이스 고유 ID (URL에서 파싱)",
    )
    naver_place_url = Column(
        String(500),
        nullable=False,
        comment="네이버 플레이스 URL",
    )

    # 업체 정보
    name = Column(
        String(200),
        nullable=False,
        comment="업체명 (크롤링으로 자동 수집)",
    )
    alias = Column(
        String(100),
        nullable=True,
        comment="워크스페이스 내 별칭 (사용자 지정)",
    )
    category = Column(
        String(100),
        nullable=True,
        comment="업체 카테고리",
    )
    address = Column(
        String(300),
        nullable=True,
        comment="업체 주소",
    )

    # 상태
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="장소 활성화 상태",
    )

    # 추가 데이터
    extra_data = Column(
        JSONB,
        nullable=True,
        default=dict,
        comment="추가 정보 (전화번호, 영업시간 등)",
    )

    # Relations
    workspace = relationship("Workspace", back_populates="places")
    keywords = relationship(
        "PlaceKeyword",
        back_populates="place",
        cascade="all, delete-orphan",
    )
    orders = relationship(
        "Order",
        back_populates="place",
    )

    def __repr__(self) -> str:
        return f"<Place {self.name} ({self.naver_place_id})>"
