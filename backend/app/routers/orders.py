"""
주문(Order) 라우터 (Sprint 5 완성)

products 라우터도 이 파일에서 함께 관리.
main.py 에서 두 가지 prefix로 각각 등록:
    - /api/v1/products  → products_router
    - /api/v1/orders    → orders_router
    - /api/v1/payments  → payments_router

엔드포인트 목록:
──────────────────────────────────────────────
[상품]
GET  /api/v1/products                       활성 상품 목록 (유형별 그룹)

[주문]
GET  /api/v1/orders                         내 주문 목록 (workspace_id, status, skip, limit)
POST /api/v1/orders                         주문 생성 + Mock 결제 페이로드 반환
GET  /api/v1/orders/{order_id}              주문 상세
POST /api/v1/orders/{order_id}/cancel       주문 취소 (pending만)
POST /api/v1/orders/{order_id}/refund-request  환불 요청 (completed/in_progress)

[결제]
POST /api/v1/payments/{payment_id}/complete  Mock PG 결제 완료 처리
──────────────────────────────────────────────
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.keyword import PlaceKeyword
from app.services.notification_service import notification_service  # Sprint 7
from app.models.order import Order, OrderStatus, Payment, PaymentMethod, PaymentStatus
from app.models.place import Place
from app.models.product import Product, ProductType
from app.models.user import User, UserRole
from app.models.workspace import MemberRole, Workspace, WorkspaceMember
from app.schemas.order import (
    CreateOrderResponse,
    OrderCreateRequest,
    OrderDetail,
    OrderListItem,
    OrderListResponse,
    PaymentCompleteRequest,
    PaymentInfo,
    ProductListResponse,
    ProductResponse,
    ProductTypeWithProducts,
    RefundRequestBody,
)

# ── 라우터 인스턴스 (3개) ─────────────────────────────────
products_router = APIRouter()
orders_router = APIRouter()
payments_router = APIRouter()


# ============================
# 내부 헬퍼 — 멤버십 검증
# ============================

def _verify_workspace_member(
    workspace_id,
    user: User,
    db: Session,
    required_roles: Optional[List[MemberRole]] = None,
) -> tuple[Workspace, WorkspaceMember]:
    """워크스페이스 멤버십 검증"""
    workspace = db.query(Workspace).filter(
        Workspace.id == workspace_id,
        Workspace.is_active == True,
    ).first()

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다",
        )

    # 어드민은 무조건 통과
    if user.role in (UserRole.ADMIN, UserRole.SUPERADMIN):
        mock = WorkspaceMember()
        mock.role = MemberRole.OWNER
        return workspace, mock

    member = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user.id,
    ).first()

    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 워크스페이스에 접근 권한이 없습니다",
        )

    if required_roles and member.role not in required_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이 작업을 수행할 권한이 없습니다",
        )

    return workspace, member


# ============================
# 내부 헬퍼 — 응답 변환
# ============================

def _product_to_response(product: Product) -> ProductResponse:
    """Product 모델 → ProductResponse 스키마 변환"""
    extra = product.extra_data or {}
    return ProductResponse(
        id=str(product.id),
        name=product.name,
        description=product.description,
        base_price=product.base_price,
        unit=product.unit,
        min_quantity=product.min_quantity,
        max_quantity=product.max_quantity,
        badge=extra.get("badge"),
        features=extra.get("features", []),
    )


def _payment_to_info(payment: Payment) -> PaymentInfo:
    """Payment 모델 → PaymentInfo 스키마 변환"""
    return PaymentInfo(
        id=str(payment.id),
        amount=payment.amount,
        method=payment.method.value if payment.method else None,
        status=payment.status.value,
        pg_transaction_id=payment.pg_transaction_id,
        paid_at=payment.paid_at,
        created_at=payment.created_at,
    )


def _order_to_detail(order: Order, db: Session) -> OrderDetail:
    """Order 모델 → OrderDetail 스키마 변환 (연관 정보 포함)"""
    # 장소 정보
    place_info = None
    if order.place_id:
        place = db.query(Place).filter(Place.id == order.place_id).first()
        if place:
            place_info = {
                "id": str(place.id),
                "name": place.name,
                "alias": place.alias,
                "naver_place_id": place.naver_place_id,
            }

    # 키워드 정보
    keyword_infos = []
    if order.keyword_ids:
        for kw_id in order.keyword_ids:
            try:
                kw = db.query(PlaceKeyword).filter(
                    PlaceKeyword.id == kw_id
                ).first()
                if kw:
                    keyword_infos.append({
                        "id": str(kw.id),
                        "keyword": kw.keyword,
                    })
            except Exception:
                pass

    # 결제 정보
    payment_info = None
    if order.payment:
        payment_info = _payment_to_info(order.payment)

    # 매체사 이름
    media_company_name = None
    if order.media_company:
        media_company_name = order.media_company.name

    return OrderDetail(
        id=str(order.id),
        product_id=str(order.product_id) if order.product_id else None,
        product_name=order.product_name,
        category=order.category.value if order.category else None,
        description=order.description,
        status=order.status.value,
        quantity=order.quantity,
        unit_price=order.unit_price,
        total_amount=order.total_amount,
        daily_qty=order.daily_qty,
        start_date=order.start_date,
        end_date=order.end_date,
        special_requests=order.special_requests,
        place=place_info,
        keywords=keyword_infos,
        payment=payment_info,
        media_company_id=str(order.media_company_id) if order.media_company_id else None,
        media_company_name=media_company_name,
        proof_url=order.proof_url,
        ordered_at=order.ordered_at,
        completed_at=order.completed_at,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


# ============================
# 상품 엔드포인트
# ============================

@products_router.get(
    "",
    response_model=ProductListResponse,
    summary="상품 목록 조회 (유형별 그룹)",
)
async def list_products(
    db: Session = Depends(get_db),
):
    """
    활성 상품 목록을 유형별로 그룹화하여 반환.
    인증 불필요 (공개 API).
    """
    # 활성 상품 유형 + 소속 활성 상품 조회
    product_types = (
        db.query(ProductType)
        .filter(ProductType.is_active == True)
        .order_by(ProductType.sort_order)
        .all()
    )

    result = []
    for pt in product_types:
        active_products = [
            _product_to_response(p)
            for p in pt.products
            if p.is_active
        ]
        if active_products:  # 상품 없는 유형은 제외
            result.append(
                ProductTypeWithProducts(
                    id=str(pt.id),
                    name=pt.name,
                    description=pt.description,
                    products=active_products,
                )
            )

    return ProductListResponse(product_types=result)


# ============================
# 주문 목록
# ============================

@orders_router.get(
    "",
    response_model=OrderListResponse,
    summary="주문 목록 조회",
)
async def list_orders(
    workspace_id: str = Query(..., description="워크스페이스 ID (필수)"),
    status_filter: Optional[str] = Query(
        None, alias="status", description="상태 필터 (없으면 전체)"
    ),
    skip: int = Query(0, ge=0, description="건너뛸 수"),
    limit: int = Query(20, ge=1, le=100, description="조회 수"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    워크스페이스의 주문 목록 조회.

    - 워크스페이스 멤버십 검증
    - status 파라미터로 필터링 가능 (없으면 전체)
    - skip/limit 페이지네이션
    """
    _verify_workspace_member(workspace_id, current_user, db)

    query = db.query(Order).filter(
        Order.workspace_id == workspace_id
    )

    # 상태 필터
    if status_filter:
        try:
            status_enum = OrderStatus(status_filter)
            query = query.filter(Order.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"유효하지 않은 상태 값: {status_filter}",
            )

    total = query.count()
    orders = (
        query
        .order_by(Order.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    items = []
    for order in orders:
        place_name = None
        if order.place_id:
            place = db.query(Place).filter(Place.id == order.place_id).first()
            if place:
                place_name = place.alias or place.name

        items.append(
            OrderListItem(
                id=str(order.id),
                product_name=order.product_name,
                status=order.status.value,
                total_amount=order.total_amount,
                quantity=order.quantity,
                unit_price=order.unit_price,
                place_name=place_name,
                ordered_at=order.ordered_at,
                created_at=order.created_at,
            )
        )

    return OrderListResponse(total=total, items=items)


# ============================
# 주문 생성
# ============================

@orders_router.post(
    "",
    response_model=CreateOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="주문 생성 + Mock 결제 페이로드 반환",
)
async def create_order(
    data: OrderCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    주문 생성.

    Flow:
        1. 워크스페이스 멤버십 검증 (owner/manager만)
        2. 상품 존재 여부 확인
        3. 장소 존재 여부 확인 (place_id 있을 경우)
        4. 키워드 존재 여부 확인 (keyword_ids 있을 경우)
        5. Order 생성 (status=pending)
        6. Payment 생성 (status=pending, method 저장)
        7. 응답: { order, payment }
    """
    # ── 1. 워크스페이스 멤버십 검증 ────────────────────────
    _verify_workspace_member(
        data.workspace_id,
        current_user,
        db,
        required_roles=[MemberRole.OWNER, MemberRole.MANAGER],
    )

    # ── 2. 상품 확인 ────────────────────────────────────────
    try:
        product_uuid = uuid.UUID(data.product_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="유효하지 않은 상품 ID 형식입니다",
        )

    product = db.query(Product).filter(
        Product.id == product_uuid,
        Product.is_active == True,
    ).first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="상품을 찾을 수 없습니다",
        )

    # 수량 최솟값 검증
    if data.quantity < product.min_quantity:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"최소 주문 수량은 {product.min_quantity}{product.unit}입니다",
        )
    if product.max_quantity and data.quantity > product.max_quantity:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"최대 주문 수량은 {product.max_quantity}{product.unit}입니다",
        )

    # ── 3. 장소 확인 ────────────────────────────────────────
    place_uuid = None
    if data.place_id:
        try:
            place_uuid = uuid.UUID(data.place_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="유효하지 않은 장소 ID 형식입니다",
            )

        place = db.query(Place).filter(
            Place.id == place_uuid,
            Place.workspace_id == uuid.UUID(data.workspace_id),
            Place.is_active == True,
        ).first()

        if not place:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="장소를 찾을 수 없습니다",
            )

    # ── 4. 키워드 확인 및 UUID 변환 ─────────────────────────
    valid_keyword_ids = []
    if data.keyword_ids:
        for kw_id_str in data.keyword_ids:
            try:
                kw_uuid = uuid.UUID(kw_id_str)
                kw = db.query(PlaceKeyword).filter(
                    PlaceKeyword.id == kw_uuid,
                    PlaceKeyword.is_active == True,
                ).first()
                if kw:
                    valid_keyword_ids.append(str(kw_uuid))
            except ValueError:
                pass  # 유효하지 않은 UUID는 무시

    # ── 5. 결제 수단 검증 ────────────────────────────────────
    try:
        payment_method_enum = PaymentMethod(data.payment_method)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"유효하지 않은 결제 수단: {data.payment_method}. (kakaopay | naverpay | card)",
        )

    # ── 6. 금액 계산 ────────────────────────────────────────
    unit_price = product.base_price
    total_amount = unit_price * data.quantity

    # ── 7. Order 생성 ────────────────────────────────────────
    # category 검증
    from app.models.order import OrderCategory
    category_enum = None
    if data.category:
        try:
            category_enum = OrderCategory(data.category)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"유효하지 않은 카테고리: {data.category}. (blog/reward_traffic/reward_save/receipt/sns)",
            )

    new_order = Order(
        id=uuid.uuid4(),
        workspace_id=uuid.UUID(data.workspace_id),
        product_id=product.id,
        place_id=place_uuid,
        keyword_ids=valid_keyword_ids,
        product_name=product.name,
        description=product.description,
        quantity=data.quantity,
        unit_price=unit_price,
        total_amount=total_amount,
        daily_qty=data.daily_qty,
        start_date=data.start_date,
        end_date=data.end_date,
        category=category_enum,
        special_requests=data.special_requests,
        status=OrderStatus.PENDING,
    )
    db.add(new_order)
    db.flush()  # order.id 확정

    # ── 8. Payment 생성 ─────────────────────────────────────
    new_payment = Payment(
        id=uuid.uuid4(),
        order_id=new_order.id,
        amount=total_amount,
        method=payment_method_enum,
        status=PaymentStatus.PENDING,
    )
    db.add(new_payment)
    db.commit()
    db.refresh(new_order)
    db.refresh(new_payment)

    # ── Sprint 7: 주문 생성 알림 발송 ───────────────────────
    try:
        await notification_service.notify_order_created(db, new_order, current_user)
        db.commit()
    except Exception as _e:
        import logging
        logging.getLogger(__name__).warning(f"주문 생성 알림 발송 실패: {_e}")

    return CreateOrderResponse(
        order=_order_to_detail(new_order, db),
        payment=_payment_to_info(new_payment),
    )


# ============================
# 주문 상세
# ============================

@orders_router.get(
    "/{order_id}",
    response_model=OrderDetail,
    summary="주문 상세 조회",
)
async def get_order(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    주문 상세 조회.
    - 본인 워크스페이스 주문만 조회 가능 (어드민 예외)
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="주문을 찾을 수 없습니다",
        )

    # 어드민이 아닌 경우 본인 워크스페이스 주문만 조회 가능
    if current_user.role not in (UserRole.ADMIN, UserRole.SUPERADMIN):
        _verify_workspace_member(str(order.workspace_id), current_user, db)

    return _order_to_detail(order, db)


# ============================
# 주문 취소
# ============================

@orders_router.post(
    "/{order_id}/cancel",
    summary="주문 취소 (pending 상태만)",
)
async def cancel_order(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    주문 취소.
    - pending 상태인 주문만 취소 가능
    - 취소 시 Payment 도 refunded 처리
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="주문을 찾을 수 없습니다",
        )

    # 본인 워크스페이스 주문인지 확인
    if current_user.role not in (UserRole.ADMIN, UserRole.SUPERADMIN):
        _verify_workspace_member(
            str(order.workspace_id),
            current_user,
            db,
            required_roles=[MemberRole.OWNER, MemberRole.MANAGER],
        )

    # pending 상태만 취소 가능
    if order.status != OrderStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="진행 중인 주문은 취소할 수 없습니다. 환불을 요청해주세요.",
        )

    order.status = OrderStatus.CANCELLED

    # 연결된 결제도 환불 처리
    if order.payment and order.payment.status == PaymentStatus.PENDING:
        order.payment.status = PaymentStatus.REFUNDED

    db.commit()

    # ── Sprint 7: 주문 취소 알림 발송 ───────────────────────
    try:
        await notification_service.notify_order_status_changed(db, order, current_user, "cancelled")
        db.commit()
    except Exception as _e:
        import logging
        logging.getLogger(__name__).warning(f"주문 취소 알림 발송 실패: {_e}")

    return {"message": "주문이 취소되었습니다", "order_id": str(order.id)}


# ============================
# 환불 요청
# ============================

@orders_router.post(
    "/{order_id}/refund-request",
    summary="환불 요청 (completed / in_progress 상태)",
)
async def request_refund(
    order_id: str,
    body: RefundRequestBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    환불 요청.
    - completed 또는 in_progress 상태에서만 요청 가능
    - 상태 → disputed
    - 어드민 알림 (현재는 콘솔 print로 대체)
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="주문을 찾을 수 없습니다",
        )

    # 본인 워크스페이스 주문인지 확인
    if current_user.role not in (UserRole.ADMIN, UserRole.SUPERADMIN):
        _verify_workspace_member(str(order.workspace_id), current_user, db)

    # 환불 요청 가능한 상태 확인
    refundable_statuses = {OrderStatus.COMPLETED, OrderStatus.IN_PROGRESS}
    if order.status not in refundable_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"현재 상태({order.status.value})에서는 환불을 요청할 수 없습니다",
        )

    order.status = OrderStatus.DISPUTED

    # extra_data에 환불 사유 기록
    if not order.extra_data:
        order.extra_data = {}
    order.extra_data["refund_reason"] = body.reason
    order.extra_data["refund_requested_at"] = datetime.now(timezone.utc).isoformat()

    db.commit()

    # ── Sprint 7: 환불 요청 알림 발송 ───────────────────────
    try:
        await notification_service.notify_order_status_changed(db, order, current_user, "refund_requested")
        db.commit()
    except Exception as _e:
        import logging
        logging.getLogger(__name__).warning(f"환불 요청 알림 발송 실패: {_e}")

    # ── Mock 어드민 알림 ─────────────────────────────────────
    print(
        f"[환불요청] 주문 {order_id} | "
        f"사유: {body.reason} | "
        f"유저: {current_user.email}"
    )

    return {
        "message": "환불 요청이 접수되었습니다. 영업일 기준 1~3일 내 처리됩니다.",
        "order_id": str(order.id),
        "status": "disputed",
    }


# ============================
# Mock PG 결제 완료
# ============================

@payments_router.post(
    "/{payment_id}/complete",
    summary="Mock PG 결제 완료 처리",
)
async def complete_payment(
    payment_id: str,
    body: PaymentCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mock PG 결제 완료 처리.

    - Payment status: pending → completed
    - Order status: pending → confirmed
    - paid_at, pg_transaction_id 기록
    - ordered_at 기록 (결제 완료 시점 = 주문 확정 시점)
    """
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="결제 정보를 찾을 수 없습니다",
        )

    order = payment.order
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="연결된 주문을 찾을 수 없습니다",
        )

    # 본인 워크스페이스 주문인지 확인
    if current_user.role not in (UserRole.ADMIN, UserRole.SUPERADMIN):
        _verify_workspace_member(str(order.workspace_id), current_user, db)

    # 이미 완료된 결제는 중복 처리 방지
    if payment.status == PaymentStatus.COMPLETED:
        return {
            "order_id": str(order.id),
            "payment_id": str(payment.id),
            "status": "confirmed",
            "message": "이미 완료된 결제입니다",
        }

    # 결제 수단 검증
    try:
        payment_method_enum = PaymentMethod(body.method)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"유효하지 않은 결제 수단: {body.method}",
        )

    now = datetime.now(timezone.utc)

    # ── Payment 업데이트 ─────────────────────────────────────
    payment.status = PaymentStatus.COMPLETED
    payment.method = payment_method_enum
    payment.pg_transaction_id = body.pg_transaction_id
    payment.paid_at = now

    # ── Order 업데이트 ───────────────────────────────────────
    order.status = OrderStatus.CONFIRMED
    order.ordered_at = now

    db.commit()

    return {
        "order_id": str(order.id),
        "payment_id": str(payment.id),
        "status": "confirmed",
        "message": "결제가 완료되었습니다. 담당자가 확인 후 작업을 시작합니다.",
    }
