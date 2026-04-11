"""
统一 HTTP 响应：code / msg / data / request_id
API 只应 return success(...) 或交由异常处理；禁止手写裸 dict。
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from fastapi import Request
from pydantic import BaseModel, Field

T = TypeVar("T")


class UnifiedResponse(BaseModel, Generic[T]):
    code: int = Field(description="0 成功，非 0 失败")
    msg: str = "success"
    data: T | None = None
    request_id: str = ""


def success(
    data: T | None = None,
    request_id: str = "",
    msg: str = "success",
) -> UnifiedResponse[T]:
    return UnifiedResponse(code=0, msg=msg, data=data, request_id=request_id or "")


def error(
    code: int,
    msg: str,
    request_id: str = "",
    data: Any = None,
) -> UnifiedResponse[Any]:
    return UnifiedResponse(code=code, msg=msg, data=data, request_id=request_id or "")


def success_for_request(request: Request, data: T | None = None, msg: str = "success") -> UnifiedResponse[T]:
    rid = getattr(request.state, "request_id", None) or ""
    return success(data=data, request_id=rid, msg=msg)


def request_id_from(request: Request) -> str:
    return getattr(request.state, "request_id", None) or ""
