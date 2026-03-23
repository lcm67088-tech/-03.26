"""
상품(Product) 모델 (Sprint 5 신규)

마케팅 서비스 상품 카탈로그 관리.
- ProductType: 상품 유형 (트래픽 / 리뷰 / 바이럴)
- Product: 실제 판매 상품 (가격, 수량 단위 등)
"""
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class ProductType(BaseModel):
    """
    상품 유형 테이블
    예: "트래픽", "리뷰", "바이럴"
    """
    __tablename__ = "product_types"
    __table_args__ = {"comment": "상품 유형 분류"}

    # 유형 이름
    name = Column(
        String(100),
        nullable=False,
        unique=True,
        comment="상품 유형명 (예: 트래픽, 리뷰, 바이럴)",
    )

    # 설명
    description = Column(
        String(500),
        nullable=True,
        comment="유형 설명",
    )

    # 활성화 여부
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="활성화 상태",
    )

    # 정렬 순서 (낮을수록 먼저 표시)
    sort_order = Column(
        Integer,
        default=0,
        nullable=False,
        comment="정렬 순서",
    )

    # Relations
    products = relationship(
        "Product",
        back_populates="product_type",
        cascade="all, delete-orphan",
        order_by="Product.sort_order",
    )

    def __repr__(self) -> str:
        return f"<ProductType {self.name}>"


class Product(BaseModel):
    """
    상품 테이블
    판매 가능한 마케팅 서비스 상품 목록.
    extra_data JSONB에 배지(badge), 특징(features) 등 저장.
    """
    __tablename__ = "products"
    __table_args__ = {"comment": "판매 상품 목록"}

    # 상품 유형 FK
    product_type_id = Column(
        UUID(as_uuid=True),
        ForeignKey("product_types.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="상품 유형 FK",
    )

    # 상품 정보
    name = Column(
        String(200),
        nullable=False,
        comment="상품명 (예: 트래픽 스탠다드)",
    )
    description = Column(
        String(1000),
        nullable=True,
        comment="상품 설명",
    )

    # 가격 정보
    base_price = Column(
        Integer,
        nullable=False,
        comment="기본 가격 (원 단위)",
    )
    unit = Column(
        String(50),
        nullable=False,
        default="건",
        comment="단위 (예: 타수, 건, 개월)",
    )

    # 수량 제한
    min_quantity = Column(
        Integer,
        nullable=False,
        default=1,
        comment="최소 주문 수량",
    )
    max_quantity = Column(
        Integer,
        nullable=True,
        comment="최대 주문 수량 (NULL=무제한)",
    )

    # 상태
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="판매 중 여부",
    )

    # 정렬 순서
    sort_order = Column(
        Integer,
        default=0,
        nullable=False,
        comment="정렬 순서",
    )

    # 추가 데이터 (배지, 특징 목록 등)
    # 예: { "badge": "인기", "features": ["7일 내 완료", "성과 리포트"] }
    extra_data = Column(
        JSONB,
        nullable=True,
        default=dict,
        comment="추가 정보 (badge, features 등) JSONB",
    )

    # Relations
    product_type = relationship("ProductType", back_populates="products")

    def __repr__(self) -> str:
        return f"<Product {self.name} {self.base_price}원>"
