"""
统一响应类型别名（实际定义在 core.response）。
"""

from typing import Generic, TypeVar

from pydantic import BaseModel

from backend.core.response import UnifiedResponse, error, success, success_for_request

T = TypeVar("T")

# 与历史命名兼容：ApiResponse[T] == UnifiedResponse[T]
ApiResponse = UnifiedResponse

__all__ = [
    "ApiResponse",
    "PagedData",
    "UnifiedResponse",
    "error",
    "success",
    "success_for_request",
]


class PagedData(BaseModel, Generic[T]):
    """分页列表通用包装（预留）。"""

    items: list[T]
    total: int
    page: int = 1
    page_size: int = 20
