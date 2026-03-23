# backend/app/schemas/__init__.py
from app.schemas.common import PaginatedResponse, MessageResponse
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.schemas.workspace import WorkspaceCreate, WorkspaceResponse, WorkspaceMemberResponse
from app.schemas.place import PlaceCreate, PlaceUpdate, PlaceDetail, PlaceListItem, PlaceListResponse
from app.schemas.keyword import KeywordCreate, KeywordResponse, RankingResponse
from app.schemas.order import (
    OrderCreateRequest, OrderListItem, OrderListResponse,
    OrderDetail, CreateOrderResponse, ProductResponse, ProductListResponse,
    ProductTypeWithProducts, PaymentCompleteRequest, RefundRequestBody,
)
from app.schemas.auth import LoginRequest, TokenResponse, RefreshRequest

# 하위 호환 alias
PlaceResponse = PlaceDetail
OrderCreate = OrderCreateRequest
OrderResponse = CreateOrderResponse
OrderUpdate = None  # placeholder (미사용)

__all__ = [
    "PaginatedResponse", "MessageResponse",
    "UserCreate", "UserResponse", "UserUpdate",
    "WorkspaceCreate", "WorkspaceResponse", "WorkspaceMemberResponse",
    "PlaceCreate", "PlaceUpdate", "PlaceDetail", "PlaceListItem", "PlaceListResponse",
    "PlaceResponse",
    "KeywordCreate", "KeywordResponse", "RankingResponse",
    "OrderCreateRequest", "OrderCreate",
    "OrderListItem", "OrderListResponse", "OrderDetail",
    "CreateOrderResponse", "OrderResponse",
    "ProductResponse", "ProductListResponse", "ProductTypeWithProducts",
    "PaymentCompleteRequest", "RefundRequestBody",
    "LoginRequest", "TokenResponse", "RefreshRequest",
]
