"""
MediaCompany 모델
실제 트래픽을 집행하는 파트너사 관리
어드민 전용, 유저에게는 비공개
"""
from sqlalchemy import Boolean, Column, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class MediaCompany(BaseModel):
    """
    매체사 테이블 (어드민 전용)
    네이버 플레이스 트래픽을 집행하는 파트너사
    
    주요 매체사 예시: Peak, NNW, 말차 등
    
    Relations:
        - orders: 배정된 주문 목록
    """
    __tablename__ = "media_companies"
    __table_args__ = {"comment": "매체사 (트래픽 집행 파트너사) - 어드민 전용"}

    # 기본 정보
    name = Column(
        String(100),
        nullable=False,
        comment="매체사명",
    )
    contact_email = Column(
        String(255),
        nullable=True,
        comment="담당자 이메일",
    )
    contact_phone = Column(
        String(20),
        nullable=True,
        comment="담당자 전화번호",
    )

    # 정산 계좌
    bank_account = Column(
        String(200),
        nullable=True,
        comment="정산 계좌 정보 (암호화 필요)",
    )

    # 상태
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="매체사 활성화 상태",
    )

    # 추가 데이터
    extra_data = Column(
        JSONB,
        nullable=True,
        default=dict,
        comment="추가 정보 (계약 조건, 처리 가능 카테고리 등)",
    )

    # Relations
    orders = relationship(
        "Order",
        back_populates="media_company",
    )
    # Sprint 9: 정산 관계
    settlements = relationship(
        "Settlement",
        back_populates="media_company",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<MediaCompany {self.name}>"
