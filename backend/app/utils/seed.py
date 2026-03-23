"""
시드 데이터 유틸리티 (Sprint 5 신규)

개발/초기 운영 환경에서 기본 상품 데이터를 DB에 삽입한다.
product_types, products 테이블이 비어 있을 때만 실행.

사용법:
    from app.utils.seed import seed_products
    seed_products(db)
"""
import uuid
from sqlalchemy.orm import Session

from app.models.product import Product, ProductType


def seed_products(db: Session) -> int:
    """
    기본 상품 데이터 시드.

    이미 product_types 데이터가 있으면 스킵한다.

    Returns:
        int: 삽입된 상품 수 (0이면 이미 시드됨)
    """
    # 이미 데이터가 있으면 스킵
    existing_count = db.query(ProductType).count()
    if existing_count > 0:
        print(f"[seed] product_types 이미 {existing_count}개 존재 → 스킵")
        return 0

    print("[seed] 상품 기본 데이터 삽입 시작...")

    # ── 상품 유형 생성 ─────────────────────────────────────
    type_traffic = ProductType(
        id=uuid.uuid4(),
        name="트래픽",
        description="네이버 플레이스 트래픽 집행 서비스",
        is_active=True,
        sort_order=1,
    )
    type_review = ProductType(
        id=uuid.uuid4(),
        name="리뷰",
        description="네이버 플레이스 리뷰 관리 서비스",
        is_active=True,
        sort_order=2,
    )
    type_viral = ProductType(
        id=uuid.uuid4(),
        name="바이럴",
        description="블로그/카페 바이럴 마케팅 서비스",
        is_active=True,
        sort_order=3,
    )

    db.add_all([type_traffic, type_review, type_viral])
    db.flush()  # ID 확정

    # ── 상품 생성 ──────────────────────────────────────────
    products = [
        # 트래픽 상품
        Product(
            id=uuid.uuid4(),
            product_type_id=type_traffic.id,
            name="트래픽 기본",
            description="네이버 플레이스 트래픽 기본 패키지. 자연스러운 방문자 유입으로 노출 순위 향상.",
            base_price=150000,
            unit="타수",
            min_quantity=100,
            max_quantity=1000,
            is_active=True,
            sort_order=1,
            extra_data={
                "badge": None,
                "features": [
                    "100타수 이상",
                    "10일 내 작업 완료",
                    "기본 성과 리포트 제공",
                ],
            },
        ),
        Product(
            id=uuid.uuid4(),
            product_type_id=type_traffic.id,
            name="트래픽 스탠다드",
            description="네이버 플레이스 트래픽 스탠다드 패키지. 다양한 키워드 타겟팅으로 효과적인 순위 개선.",
            base_price=280000,
            unit="타수",
            min_quantity=200,
            max_quantity=2000,
            is_active=True,
            sort_order=2,
            extra_data={
                "badge": "인기",
                "features": [
                    "200타수 이상",
                    "7일 내 작업 완료",
                    "상세 성과 리포트 제공",
                    "키워드별 맞춤 집행",
                ],
            },
        ),
        Product(
            id=uuid.uuid4(),
            product_type_id=type_traffic.id,
            name="트래픽 프리미엄",
            description="네이버 플레이스 트래픽 프리미엄 패키지. 대용량 트래픽으로 빠른 순위 상승 효과.",
            base_price=500000,
            unit="타수",
            min_quantity=500,
            max_quantity=5000,
            is_active=True,
            sort_order=3,
            extra_data={
                "badge": "추천",
                "features": [
                    "500타수 이상",
                    "5일 내 작업 완료",
                    "프리미엄 성과 리포트",
                    "전담 매니저 배정",
                    "1회 무료 재작업",
                ],
            },
        ),
        # 리뷰 상품
        Product(
            id=uuid.uuid4(),
            product_type_id=type_review.id,
            name="리뷰 케어 기본",
            description="네이버 플레이스 리뷰 관리 기본 패키지. 자연스러운 긍정 리뷰 생성.",
            base_price=200000,
            unit="건",
            min_quantity=10,
            max_quantity=100,
            is_active=True,
            sort_order=1,
            extra_data={
                "badge": None,
                "features": [
                    "10건 이상",
                    "네이버 아이디 다양화",
                    "14일 내 작업 완료",
                ],
            },
        ),
        Product(
            id=uuid.uuid4(),
            product_type_id=type_review.id,
            name="리뷰 케어 프리미엄",
            description="네이버 플레이스 리뷰 관리 프리미엄 패키지. 키워드 포함 고품질 리뷰 생성.",
            base_price=450000,
            unit="건",
            min_quantity=20,
            max_quantity=200,
            is_active=True,
            sort_order=2,
            extra_data={
                "badge": "인기",
                "features": [
                    "20건 이상",
                    "키워드 자연 삽입",
                    "10일 내 작업 완료",
                    "사진 포함 리뷰",
                    "리뷰 품질 보증",
                ],
            },
        ),
        # 바이럴 상품
        Product(
            id=uuid.uuid4(),
            product_type_id=type_viral.id,
            name="블로그 바이럴",
            description="네이버 블로그를 활용한 바이럴 마케팅. 키워드 상위 노출로 간접 홍보 효과.",
            base_price=300000,
            unit="건",
            min_quantity=5,
            max_quantity=50,
            is_active=True,
            sort_order=1,
            extra_data={
                "badge": None,
                "features": [
                    "5건 이상",
                    "네이버 블로그 최적화",
                    "키워드 SEO 적용",
                    "14일 내 작업 완료",
                ],
            },
        ),
        Product(
            id=uuid.uuid4(),
            product_type_id=type_viral.id,
            name="카페 바이럴",
            description="네이버 카페를 활용한 바이럴 마케팅. 지역 커뮤니티 기반 자연스러운 홍보.",
            base_price=250000,
            unit="건",
            min_quantity=5,
            max_quantity=50,
            is_active=True,
            sort_order=2,
            extra_data={
                "badge": None,
                "features": [
                    "5건 이상",
                    "지역 카페 중심 포스팅",
                    "자연스러운 후기 형태",
                    "10일 내 작업 완료",
                ],
            },
        ),
    ]

    db.add_all(products)
    db.commit()

    total = len(products)
    print(f"[seed] 상품 {total}개 삽입 완료")
    return total
