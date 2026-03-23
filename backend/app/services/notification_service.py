"""
알림 서비스 모듈
Sprint 7: 알림 생성, 채널별 발송(Mock), 편의 메서드 제공
- NOTIFICATION_TEMPLATES: 25가지 알림 제목/메시지 템플릿
- NotificationService: 알림 생성 및 채널 발송 서비스 클래스
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationType
from app.models.notification_setting import NotificationSetting

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# 알림 템플릿 딕셔너리
# key: NotificationType, value: {"title": str, "message": str}
# {변수}는 data dict 값으로 포맷팅됨
# ─────────────────────────────────────────────────────────────
NOTIFICATION_TEMPLATES: Dict[NotificationType, Dict[str, str]] = {
    # ── 주문 관련 알림 (8가지) ──────────────────────────────
    NotificationType.ORDER_CREATED: {
        "title": "주문이 접수되었습니다",
        "message": "주문번호 {order_number} 가 정상적으로 접수되었습니다. 검토 후 확인 안내를 드립니다.",
    },
    NotificationType.ORDER_CONFIRMED: {
        "title": "주문이 확인되었습니다",
        "message": "주문번호 {order_number} 가 확인되었습니다. 곧 매체사에 배정될 예정입니다.",
    },
    NotificationType.ORDER_ASSIGNED: {
        "title": "매체사가 배정되었습니다",
        "message": "주문번호 {order_number} 에 매체사가 배정되었습니다. 작업이 곧 시작됩니다.",
    },
    NotificationType.ORDER_IN_PROGRESS: {
        "title": "주문 작업이 시작되었습니다",
        "message": "주문번호 {order_number} 작업이 진행 중입니다.",
    },
    NotificationType.ORDER_COMPLETED: {
        "title": "주문이 완료되었습니다",
        "message": "주문번호 {order_number} 작업이 완료되었습니다. 결과를 확인해보세요.",
    },
    NotificationType.ORDER_CANCELLED: {
        "title": "주문이 취소되었습니다",
        "message": "주문번호 {order_number} 가 취소되었습니다.",
    },
    NotificationType.ORDER_REFUND_REQUESTED: {
        "title": "환불이 요청되었습니다",
        "message": "주문번호 {order_number} 에 대한 환불 요청이 접수되었습니다. 검토 후 결정 안내를 드립니다.",
    },
    NotificationType.ORDER_REFUND_DECIDED: {
        "title": "환불 결정이 완료되었습니다",
        "message": "주문번호 {order_number} 환불 요청에 대한 결정이 완료되었습니다. 내역을 확인해주세요.",
    },
    # ── 랭킹 관련 알림 (5가지) ──────────────────────────────
    NotificationType.RANK_IMPROVED: {
        "title": "키워드 순위가 상승했습니다",
        "message": "'{place_name}'의 키워드 '{keyword}' 순위가 {old_rank}위에서 {new_rank}위로 상승했습니다.",
    },
    NotificationType.RANK_DROPPED: {
        "title": "키워드 순위가 하락했습니다",
        "message": "'{place_name}'의 키워드 '{keyword}' 순위가 {old_rank}위에서 {new_rank}위로 하락했습니다.",
    },
    NotificationType.RANK_TOP10: {
        "title": "상위 10위에 진입했습니다",
        "message": "'{place_name}'의 키워드 '{keyword}' 가 상위 10위({new_rank}위)에 진입했습니다!",
    },
    NotificationType.RANK_TOP3: {
        "title": "상위 3위에 진입했습니다",
        "message": "'{place_name}'의 키워드 '{keyword}' 가 상위 3위({new_rank}위)에 진입했습니다! 🎉",
    },
    NotificationType.RANK_FLUCTUATION: {
        "title": "키워드 순위 급변동이 감지되었습니다",
        "message": "'{place_name}'의 키워드 '{keyword}' 순위가 {old_rank}위에서 {new_rank}위로 급변동했습니다.",
    },
    # ── 시스템 관련 알림 (5가지) ────────────────────────────
    NotificationType.PLAN_UPGRADED: {
        "title": "플랜이 업그레이드되었습니다",
        "message": "{old_plan} 플랜에서 {new_plan} 플랜으로 업그레이드되었습니다.",
    },
    NotificationType.PLAN_DOWNGRADED: {
        "title": "플랜이 다운그레이드되었습니다",
        "message": "{old_plan} 플랜에서 {new_plan} 플랜으로 변경되었습니다.",
    },
    NotificationType.PLAN_EXPIRED: {
        "title": "플랜이 만료되었습니다",
        "message": "{old_plan} 플랜이 만료되었습니다. 서비스 이용을 위해 플랜을 갱신해주세요.",
    },
    NotificationType.CRAWL_COMPLETED: {
        "title": "키워드 순위 조회가 완료되었습니다",
        "message": "워크스페이스 내 {place_count}개 플레이스의 키워드 순위 조회가 완료되었습니다.",
    },
    NotificationType.CRAWL_FAILED: {
        "title": "키워드 순위 조회에 실패했습니다",
        "message": "워크스페이스 내 키워드 순위 조회 중 오류가 발생했습니다. 잠시 후 다시 시도됩니다.",
    },
    # ── 워크스페이스 관련 알림 (4가지) ──────────────────────
    NotificationType.MEMBER_INVITED: {
        "title": "워크스페이스에 초대되었습니다",
        "message": "'{workspace_name}' 워크스페이스에 초대되었습니다.",
    },
    NotificationType.MEMBER_JOINED: {
        "title": "새 멤버가 합류했습니다",
        "message": "'{target_user_name}' 님이 '{workspace_name}' 워크스페이스에 합류했습니다.",
    },
    NotificationType.MEMBER_LEFT: {
        "title": "멤버가 워크스페이스를 떠났습니다",
        "message": "'{target_user_name}' 님이 '{workspace_name}' 워크스페이스를 떠났습니다.",
    },
    NotificationType.MEMBER_ROLE_CHANGED: {
        "title": "워크스페이스 역할이 변경되었습니다",
        "message": "'{workspace_name}' 워크스페이스에서 '{target_user_name}' 님의 역할이 변경되었습니다.",
    },
    # ── 결제 관련 알림 (3가지) ──────────────────────────────
    NotificationType.PAYMENT_COMPLETED: {
        "title": "결제가 완료되었습니다",
        "message": "{amount:,}원 결제가 성공적으로 처리되었습니다.",
    },
    NotificationType.PAYMENT_FAILED: {
        "title": "결제에 실패했습니다",
        "message": "{amount:,}원 결제 처리에 실패했습니다. 결제 수단을 확인해주세요.",
    },
    NotificationType.PAYMENT_REFUNDED: {
        "title": "환불이 처리되었습니다",
        "message": "{amount:,}원 환불이 처리되었습니다.",
    },
}


class NotificationService:
    """
    알림 서비스 클래스

    - create_notification: DB에 알림 저장 + 채널별 발송
    - get_user_settings: 사용자 알림 설정 조회 (없으면 기본값)
    - send_in_app: 인앱 알림 저장 (DB 저장)
    - send_email: 이메일 발송 (Mock 로깅)
    - send_kakao: 카카오 발송 (Mock 로깅)
    - send_sms: SMS 발송 (Mock 로깅)
    - 편의 메서드: notify_order_created, notify_order_status_changed,
                   notify_rank_changed
    """

    # ─────────────────────────────────────────────────────────
    # 핵심 메서드: 알림 생성 및 발송
    # ─────────────────────────────────────────────────────────

    async def create_notification(
        self,
        db: Session,
        user_id: UUID,
        notification_type: NotificationType,
        data: Dict[str, Any],
        workspace_id: Optional[UUID] = None,
    ) -> Notification:
        """
        알림을 생성하고 사용자 설정에 따라 각 채널로 발송합니다.

        1. 템플릿에서 title/message 포맷팅
        2. DB에 Notification 레코드 저장
        3. 사용자 설정 조회
        4. 설정에 따라 이메일/카카오/SMS Mock 발송
        """
        # 템플릿 조회 및 포맷팅
        template = NOTIFICATION_TEMPLATES.get(notification_type)
        if not template:
            logger.warning(f"알림 템플릿 없음: {notification_type}")
            title = str(notification_type)
            message = str(data)
        else:
            try:
                title = template["title"].format(**data)
                message = template["message"].format(**data)
            except KeyError as e:
                # 포맷팅 키 누락 시 원본 템플릿 사용
                logger.warning(f"알림 포맷팅 키 누락: {e}, type={notification_type}")
                title = template["title"]
                message = template["message"]

        # DB에 알림 레코드 저장
        notification = Notification(
            user_id=user_id,
            workspace_id=workspace_id,
            type=notification_type,
            title=title,
            message=message,
            data=data,
            is_read=False,
            created_at=datetime.utcnow(),
        )
        db.add(notification)
        db.flush()  # id 생성을 위해 flush (commit은 라우터에서)

        # 사용자 설정 조회
        settings = self.get_user_settings(db, user_id, notification_type)

        # 인앱 알림 (DB 저장 = 이미 완료)
        if settings.get("in_app_enabled", True):
            logger.info(
                f"[인앱 알림] user_id={user_id} type={notification_type} title={title}"
            )

        # 이메일 발송 (Mock)
        if settings.get("email_enabled", False):
            self.send_email(user_id=user_id, title=title, message=message)

        # 카카오 발송 (Mock)
        if settings.get("kakao_enabled", False):
            self.send_kakao(user_id=user_id, message=message)

        # SMS 발송 (Mock)
        if settings.get("sms_enabled", False):
            self.send_sms(user_id=user_id, message=message)

        return notification

    def get_user_settings(
        self,
        db: Session,
        user_id: UUID,
        notification_type: NotificationType,
    ) -> Dict[str, bool]:
        """
        특정 알림 타입에 대한 사용자 설정을 반환합니다.
        DB에 설정이 없으면 기본값 (in_app=True, 나머지=False) 반환.
        """
        setting = (
            db.query(NotificationSetting)
            .filter(
                NotificationSetting.user_id == user_id,
                NotificationSetting.notification_type == notification_type,
            )
            .first()
        )

        if setting is None:
            return {
                "in_app_enabled": True,
                "email_enabled": False,
                "kakao_enabled": False,
                "sms_enabled": False,
            }

        return {
            "in_app_enabled": setting.in_app_enabled,
            "email_enabled": setting.email_enabled,
            "kakao_enabled": setting.kakao_enabled,
            "sms_enabled": setting.sms_enabled,
        }

    def get_all_user_settings(
        self,
        db: Session,
        user_id: UUID,
    ) -> Dict[NotificationType, Dict[str, bool]]:
        """
        사용자의 모든 알림 타입 설정을 한 번에 조회합니다.
        DB에 없는 타입은 기본값으로 채워서 반환합니다.
        """
        db_settings = (
            db.query(NotificationSetting)
            .filter(NotificationSetting.user_id == user_id)
            .all()
        )

        settings_map: Dict[NotificationType, Dict[str, bool]] = {}
        for s in db_settings:
            settings_map[s.notification_type] = {
                "in_app_enabled": s.in_app_enabled,
                "email_enabled": s.email_enabled,
                "kakao_enabled": s.kakao_enabled,
                "sms_enabled": s.sms_enabled,
            }

        default_setting = {
            "in_app_enabled": True,
            "email_enabled": False,
            "kakao_enabled": False,
            "sms_enabled": False,
        }
        for ntype in NotificationType:
            if ntype not in settings_map:
                settings_map[ntype] = default_setting.copy()

        return settings_map

    # ─────────────────────────────────────────────────────────
    # 채널별 발송 메서드 (Mock 구현)
    # ─────────────────────────────────────────────────────────

    def send_in_app(self, db: Session, notification: Notification) -> None:
        """인앱 알림 저장 확인 로그"""
        logger.info(
            f"[인앱] 알림 저장 완료: id={notification.id} "
            f"type={notification.type} user_id={notification.user_id}"
        )

    def send_email(self, user_id: UUID, title: str, message: str) -> None:
        """이메일 발송 Mock - 실제 구현 시 SendGrid/SES 사용"""
        logger.info(
            f"[Mock 이메일] user_id={user_id} | 제목: {title} | 내용: {message}"
        )

    def send_kakao(self, user_id: UUID, message: str) -> None:
        """카카오 알림톡 발송 Mock - 실제 구현 시 카카오 비즈메시지 API 사용"""
        logger.info(
            f"[Mock 카카오] user_id={user_id} | 내용: {message}"
        )

    def send_sms(self, user_id: UUID, message: str) -> None:
        """SMS 발송 Mock - 실제 구현 시 NCP SMS/Twilio 사용"""
        logger.info(
            f"[Mock SMS] user_id={user_id} | 내용: {message}"
        )

    # ─────────────────────────────────────────────────────────
    # 편의 메서드: 주문 알림
    # ─────────────────────────────────────────────────────────

    async def notify_order_created(
        self,
        db: Session,
        order: Any,
        user: Any,
    ) -> Optional[Notification]:
        """주문 생성 알림 발송"""
        try:
            data = {
                "order_id": str(order.id),
                "order_number": getattr(order, "order_number", str(order.id)[:8].upper()),
            }
            return await self.create_notification(
                db=db,
                user_id=user.id,
                notification_type=NotificationType.ORDER_CREATED,
                data=data,
                workspace_id=getattr(order, "workspace_id", None),
            )
        except Exception as e:
            logger.error(f"주문 생성 알림 발송 실패: {e}")
            return None

    async def notify_order_status_changed(
        self,
        db: Session,
        order: Any,
        user: Any,
        status: str,
    ) -> Optional[Notification]:
        """
        주문 상태 변경 알림 발송

        status → NotificationType 매핑:
          confirmed       → ORDER_CONFIRMED
          assigned        → ORDER_ASSIGNED
          in_progress     → ORDER_IN_PROGRESS
          completed       → ORDER_COMPLETED
          cancelled       → ORDER_CANCELLED
          refund_requested→ ORDER_REFUND_REQUESTED
          refund_decided  → ORDER_REFUND_DECIDED
        """
        status_type_map: Dict[str, NotificationType] = {
            "confirmed": NotificationType.ORDER_CONFIRMED,
            "assigned": NotificationType.ORDER_ASSIGNED,
            "in_progress": NotificationType.ORDER_IN_PROGRESS,
            "completed": NotificationType.ORDER_COMPLETED,
            "cancelled": NotificationType.ORDER_CANCELLED,
            "refund_requested": NotificationType.ORDER_REFUND_REQUESTED,
            "refund_decided": NotificationType.ORDER_REFUND_DECIDED,
        }

        notification_type = status_type_map.get(status)
        if not notification_type:
            logger.warning(f"알림 매핑 없는 주문 상태: {status}")
            return None

        try:
            data = {
                "order_id": str(order.id),
                "order_number": getattr(order, "order_number", str(order.id)[:8].upper()),
            }
            return await self.create_notification(
                db=db,
                user_id=user.id,
                notification_type=notification_type,
                data=data,
                workspace_id=getattr(order, "workspace_id", None),
            )
        except Exception as e:
            logger.error(f"주문 상태 변경 알림 발송 실패: {e}")
            return None

    # ─────────────────────────────────────────────────────────
    # 편의 메서드: 랭킹 알림
    # ─────────────────────────────────────────────────────────

    async def notify_rank_changed(
        self,
        db: Session,
        keyword: Any,
        user: Any,
        old_rank: int,
        new_rank: int,
    ) -> Optional[Notification]:
        """
        랭킹 변동 알림 발송 (조건별 타입 자동 선택)

        발동 조건 (우선순위 순):
          RANK_TOP3       : new_rank <= 3 and old_rank > 3
          RANK_TOP10      : new_rank <= 10 and old_rank > 10
          RANK_FLUCTUATION: abs(new_rank - old_rank) >= 5
          RANK_IMPROVED   : new_rank < old_rank (상승)
          RANK_DROPPED    : new_rank - old_rank >= 3 (3단계 이상 하락)
        """
        diff = new_rank - old_rank  # 음수 = 상승

        if new_rank <= 3 and old_rank > 3:
            notification_type = NotificationType.RANK_TOP3
        elif new_rank <= 10 and old_rank > 10:
            notification_type = NotificationType.RANK_TOP10
        elif abs(diff) >= 5:
            notification_type = NotificationType.RANK_FLUCTUATION
        elif diff < 0:
            notification_type = NotificationType.RANK_IMPROVED
        elif diff >= 3:
            notification_type = NotificationType.RANK_DROPPED
        else:
            # 알림 발동 조건 미충족
            return None

        try:
            place = getattr(keyword, "place", None)
            place_name = getattr(place, "name", "알 수 없는 플레이스") if place else "알 수 없는 플레이스"
            data = {
                "place_id": str(getattr(keyword, "place_id", "")),
                "place_name": place_name,
                "keyword": getattr(keyword, "keyword", ""),
                "old_rank": old_rank,
                "new_rank": new_rank,
            }
            workspace_id = getattr(place, "workspace_id", None) if place else None
            return await self.create_notification(
                db=db,
                user_id=user.id,
                notification_type=notification_type,
                data=data,
                workspace_id=workspace_id,
            )
        except Exception as e:
            logger.error(f"랭킹 변동 알림 발송 실패: {e}")
            return None


# ─────────────────────────────────────────────────────────────
# 싱글톤 인스턴스 (라우터에서 직접 import해서 사용)
# ─────────────────────────────────────────────────────────────
notification_service = NotificationService()
