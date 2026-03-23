"""
알림 라우터 모듈
Sprint 7: 알림 CRUD 및 설정 엔드포인트 (7개)

엔드포인트 목록:
  GET    /api/v1/notifications              - 알림 목록 조회 (페이지네이션)
  GET    /api/v1/notifications/unread-count - 읽지 않은 알림 수
  PUT    /api/v1/notifications/read-all     - 전체 읽음 처리
  PUT    /api/v1/notifications/{id}/read    - 단건 읽음 처리
  DELETE /api/v1/notifications/{id}         - 알림 삭제
  GET    /api/v1/notifications/settings     - 알림 설정 조회
  PUT    /api/v1/notifications/settings     - 알림 설정 업데이트 (upsert)
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.notification import Notification, NotificationType
from app.models.notification_setting import NotificationSetting
from app.models.user import User
from app.schemas.notification import (
    BulkMarkReadRequest,
    NotificationListResponse,
    NotificationResponse,
    NotificationSettingItem,
    NotificationSettingResponse,
    NotificationSettingUpdate,
    UnreadCountResponse,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ─────────────────────────────────────────────────────────────
# GET /notifications - 알림 목록 조회
# ─────────────────────────────────────────────────────────────

@router.get("", response_model=NotificationListResponse)
def get_notifications(
    page: int = Query(1, ge=1, description="페이지 번호 (1부터 시작)"),
    limit: int = Query(20, ge=1, le=100, description="페이지당 항목 수 (최대 100)"),
    is_read: Optional[bool] = Query(None, description="읽음 여부 필터 (None=전체)"),
    type: Optional[NotificationType] = Query(None, description="알림 타입 필터"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    현재 로그인한 사용자의 알림 목록을 조회합니다.
    - 페이지네이션: page, limit (기본값 20개)
    - 필터: is_read (읽음/미읽음), type (알림 타입)
    - 정렬: 최신순 (created_at DESC)
    """
    # 기본 쿼리: 현재 사용자의 알림만
    query = db.query(Notification).filter(
        Notification.user_id == current_user.id
    )

    # 읽음 여부 필터
    if is_read is not None:
        query = query.filter(Notification.is_read == is_read)

    # 알림 타입 필터
    if type is not None:
        query = query.filter(Notification.type == type)

    # 전체 수 조회
    total = query.count()

    # 읽지 않은 알림 수 조회
    unread_count = (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
        .count()
    )

    # 페이지네이션 적용 (최신순)
    offset = (page - 1) * limit
    notifications = (
        query.order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in notifications],
        total=total,
        unread_count=unread_count,
        page=page,
        limit=limit,
    )


# ─────────────────────────────────────────────────────────────
# GET /notifications/unread-count - 읽지 않은 알림 수
# ─────────────────────────────────────────────────────────────

@router.get("/unread-count", response_model=UnreadCountResponse)
def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    현재 사용자의 읽지 않은 알림 수를 타입별로 반환합니다.
    """
    # 읽지 않은 알림 전체 조회
    unread_notifications = (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
        .all()
    )

    # 타입별 집계
    by_type: dict = {}
    for n in unread_notifications:
        key = n.type.value  # enum → str 변환
        by_type[key] = by_type.get(key, 0) + 1

    return UnreadCountResponse(
        total=len(unread_notifications),
        by_type=by_type,
    )


# ─────────────────────────────────────────────────────────────
# PUT /notifications/read-all - 전체 읽음 처리
# ─────────────────────────────────────────────────────────────

@router.put("/read-all")
def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    현재 사용자의 읽지 않은 모든 알림을 읽음 처리합니다.
    """
    now = datetime.utcnow()

    # 현재 사용자의 읽지 않은 알림 일괄 업데이트
    updated_count = (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
        .update(
            {"is_read": True, "read_at": now},
            synchronize_session=False,
        )
    )
    db.commit()

    return {"message": f"{updated_count}개의 알림을 읽음 처리했습니다.", "count": updated_count}


# ─────────────────────────────────────────────────────────────
# PUT /notifications/{notification_id}/read - 단건 읽음 처리
# ─────────────────────────────────────────────────────────────

@router.put("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    특정 알림을 읽음 처리합니다.
    본인 알림이 아닌 경우 403 반환.
    """
    # 알림 조회
    notification = db.query(Notification).filter(
        Notification.id == notification_id
    ).first()

    if not notification:
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")

    # 본인 알림인지 확인
    if notification.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="본인의 알림만 수정할 수 있습니다.")

    # 이미 읽음 처리된 경우 그대로 반환
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        db.commit()
        db.refresh(notification)

    return NotificationResponse.model_validate(notification)


# ─────────────────────────────────────────────────────────────
# DELETE /notifications/{notification_id} - 알림 삭제
# ─────────────────────────────────────────────────────────────

@router.delete("/{notification_id}", status_code=204)
def delete_notification(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    특정 알림을 삭제합니다.
    본인 알림이 아닌 경우 403 반환.
    """
    notification = db.query(Notification).filter(
        Notification.id == notification_id
    ).first()

    if not notification:
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")

    # 본인 알림인지 확인
    if notification.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="본인의 알림만 삭제할 수 있습니다.")

    db.delete(notification)
    db.commit()

    # 204 No Content 반환 (내용 없음)
    return None


# ─────────────────────────────────────────────────────────────
# GET /notifications/settings - 알림 설정 조회
# ─────────────────────────────────────────────────────────────

@router.get("/settings", response_model=NotificationSettingResponse)
def get_notification_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    현재 사용자의 알림 설정을 25가지 타입 전체에 대해 반환합니다.
    DB에 설정이 없는 타입은 기본값 (in_app=True, 나머지=False)으로 반환.
    """
    # DB에서 사용자 설정 조회
    db_settings = (
        db.query(NotificationSetting)
        .filter(NotificationSetting.user_id == current_user.id)
        .all()
    )

    # DB 설정을 dict로 변환
    settings_map = {s.notification_type: s for s in db_settings}

    # 25가지 타입 모두에 대해 설정 생성 (없으면 기본값)
    result_settings = []
    for ntype in NotificationType:
        if ntype in settings_map:
            s = settings_map[ntype]
            result_settings.append(
                NotificationSettingItem(
                    notification_type=ntype,
                    in_app_enabled=s.in_app_enabled,
                    email_enabled=s.email_enabled,
                    kakao_enabled=s.kakao_enabled,
                    sms_enabled=s.sms_enabled,
                )
            )
        else:
            # 기본값: 인앱만 활성화
            result_settings.append(
                NotificationSettingItem(
                    notification_type=ntype,
                    in_app_enabled=True,
                    email_enabled=False,
                    kakao_enabled=False,
                    sms_enabled=False,
                )
            )

    return NotificationSettingResponse(settings=result_settings)


# ─────────────────────────────────────────────────────────────
# PUT /notifications/settings - 알림 설정 업데이트 (upsert)
# ─────────────────────────────────────────────────────────────

@router.put("/settings", response_model=NotificationSettingResponse)
def update_notification_settings(
    body: NotificationSettingUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    알림 설정을 업데이트합니다. (upsert: 있으면 update, 없으면 insert)
    요청 body의 settings 배열에 있는 타입만 업데이트되며,
    나머지 타입은 기존 설정 유지.
    """
    now = datetime.utcnow()

    for item in body.settings:
        # 기존 설정 조회
        existing = (
            db.query(NotificationSetting)
            .filter(
                NotificationSetting.user_id == current_user.id,
                NotificationSetting.notification_type == item.notification_type,
            )
            .first()
        )

        if existing:
            # 기존 설정 업데이트
            existing.in_app_enabled = item.in_app_enabled
            existing.email_enabled = item.email_enabled
            existing.kakao_enabled = item.kakao_enabled
            existing.sms_enabled = item.sms_enabled
            existing.updated_at = now
        else:
            # 새 설정 삽입
            new_setting = NotificationSetting(
                user_id=current_user.id,
                notification_type=item.notification_type,
                in_app_enabled=item.in_app_enabled,
                email_enabled=item.email_enabled,
                kakao_enabled=item.kakao_enabled,
                sms_enabled=item.sms_enabled,
                created_at=now,
                updated_at=now,
            )
            db.add(new_setting)

    db.commit()

    # 업데이트된 전체 설정 반환 (25가지 타입 포함)
    db_settings = (
        db.query(NotificationSetting)
        .filter(NotificationSetting.user_id == current_user.id)
        .all()
    )
    settings_map = {s.notification_type: s for s in db_settings}

    result_settings = []
    for ntype in NotificationType:
        if ntype in settings_map:
            s = settings_map[ntype]
            result_settings.append(
                NotificationSettingItem(
                    notification_type=ntype,
                    in_app_enabled=s.in_app_enabled,
                    email_enabled=s.email_enabled,
                    kakao_enabled=s.kakao_enabled,
                    sms_enabled=s.sms_enabled,
                )
            )
        else:
            result_settings.append(
                NotificationSettingItem(
                    notification_type=ntype,
                    in_app_enabled=True,
                    email_enabled=False,
                    kakao_enabled=False,
                    sms_enabled=False,
                )
            )

    return NotificationSettingResponse(settings=result_settings)
