# backend/app/models/__init__.py
# 모든 모델을 여기서 임포트해야 Alembic이 마이그레이션을 인식함
from app.models.base import BaseModel
from app.models.user import User, UserRole
from app.models.workspace import Workspace, WorkspaceMember, WorkspacePlan, MemberRole
from app.models.place import Place
from app.models.keyword import PlaceKeyword, KeywordRanking, RankCaseType
from app.models.product import ProductType, Product          # Sprint 5 신규
from app.models.media_company import MediaCompany
from app.models.order import Order, OrderStatus, Payment, PaymentMethod, PaymentStatus
from app.models.crawl_job import CrawlJob, CrawlJobStatus    # Sprint 4 신규
from app.models.notification import Notification, NotificationType          # Sprint 7 신규
from app.models.notification_setting import NotificationSetting             # Sprint 7 신규
from app.models.subscription import Subscription, BillingHistory            # Sprint 8 신규
from app.models.settlement import Settlement, SettlementItem                # Sprint 9 신규

__all__ = [
    "BaseModel",
    "User", "UserRole",
    "Workspace", "WorkspaceMember", "WorkspacePlan", "MemberRole",
    "Place",
    "PlaceKeyword", "KeywordRanking", "RankCaseType",
    "ProductType", "Product",           # Sprint 5 신규
    "MediaCompany",
    "Order", "OrderStatus", "Payment", "PaymentMethod", "PaymentStatus",
    "CrawlJob", "CrawlJobStatus",       # Sprint 4 신규
    "Notification", "NotificationType", # Sprint 7 신규
    "NotificationSetting",              # Sprint 7 신규
    "Subscription", "BillingHistory",   # Sprint 8 신규
    "Settlement", "SettlementItem",     # Sprint 9 신규
]
