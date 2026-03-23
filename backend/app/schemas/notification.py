"""
알림 스키마 모듈
Sprint 7: 알림 시스템 Pydantic v2 DTO 정의
- NotificationResponse: 단일 알림 응답
- NotificationListResponse: 목록 + 페이지네이션 응답
- UnreadCountResponse: 읽지 않은 알림 수 응답
- NotificationSettingItem: 단일 알림 설정 항목
- NotificationSettingResponse: 전체 설정 응답
- NotificationSettingUpdate: 설정 업데이트 요청
- BulkMarkReadRequest: 일괄 읽음 처리 요청
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.notification import NotificationType


# ─────────────────────────────────────────────────────────────
# 알림 응답 스키마
# ─────────────────────────────────────────────────────────────

class NotificationResponse(BaseModel):
    """단일 알림 응답 스키마"""

    id: UUID = Field(..., description="알림 고유 식별자")
    type: NotificationType = Field(..., description="알림 타입")
    title: str = Field(..., description="알림 제목")
    message: str = Field(..., description="알림 본문 메시지")
    data: Dict = Field(default_factory=dict, description="알림 타입별 추가 데이터")
    is_read: bool = Field(..., description="읽음 여부")
    created_at: datetime = Field(..., description="알림 생성 시각 (UTC)")
    read_at: Optional[datetime] = Field(None, description="알림 읽은 시각 (UTC)")
    workspace_id: Optional[UUID] = Field(None, description="관련 워크스페이스 ID")

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    """알림 목록 + 페이지네이션 응답 스키마"""

    items: List[NotificationResponse] = Field(..., description="알림 목록")
    total: int = Field(..., description="전체 알림 수")
    unread_count: int = Field(..., description="읽지 않은 알림 수")
    page: int = Field(..., description="현재 페이지 번호 (1부터 시작)")
    limit: int = Field(..., description="페이지당 항목 수")

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────
# 읽지 않은 알림 수 응답
# ─────────────────────────────────────────────────────────────

class UnreadCountResponse(BaseModel):
    """읽지 않은 알림 수 응답 스키마"""

    total: int = Field(..., description="전체 읽지 않은 알림 수")
    by_type: Dict[str, int] = Field(
        default_factory=dict,
        description="알림 타입별 읽지 않은 수 (key: NotificationType 문자열)",
    )

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────
# 알림 설정 스키마
# ─────────────────────────────────────────────────────────────

class NotificationSettingItem(BaseModel):
    """단일 알림 타입 설정 항목 스키마"""

    notification_type: NotificationType = Field(..., description="알림 타입")
    in_app_enabled: bool = Field(True, description="인앱 알림 수신 여부 (기본값: True)")
    email_enabled: bool = Field(False, description="이메일 알림 수신 여부 (기본값: False)")
    kakao_enabled: bool = Field(False, description="카카오 알림 수신 여부 (기본값: False)")
    sms_enabled: bool = Field(False, description="SMS 알림 수신 여부 (기본값: False)")

    model_config = {"from_attributes": True}


class NotificationSettingResponse(BaseModel):
    """알림 설정 전체 응답 스키마 (25가지 타입 모두 포함)"""

    settings: List[NotificationSettingItem] = Field(
        ..., description="알림 타입별 설정 목록 (25개)"
    )

    model_config = {"from_attributes": True}


class NotificationSettingUpdate(BaseModel):
    """알림 설정 업데이트 요청 스키마"""

    settings: List[NotificationSettingItem] = Field(
        ..., description="업데이트할 알림 설정 목록"
    )


# ─────────────────────────────────────────────────────────────
# 일괄 읽음 처리 요청
# ─────────────────────────────────────────────────────────────

class BulkMarkReadRequest(BaseModel):
    """
    일괄 읽음 처리 요청 스키마

    notification_ids가 None이면 현재 사용자의 모든 알림을 읽음 처리.
    notification_ids에 UUID 리스트를 전달하면 해당 알림만 읽음 처리.
    """

    notification_ids: Optional[List[UUID]] = Field(
        None,
        description="읽음 처리할 알림 ID 목록. None이면 전체 읽음 처리.",
    )
