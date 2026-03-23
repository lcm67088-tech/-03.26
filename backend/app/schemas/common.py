"""
공통 스키마
페이지네이션, 메시지 응답 등
"""
from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """페이지네이션 응답"""
    items: List[T]
    total: int
    page: int
    size: int
    pages: int


class MessageResponse(BaseModel):
    """단순 메시지 응답"""
    message: str
    success: bool = True
