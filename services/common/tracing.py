from __future__ import annotations

import uuid
from contextvars import ContextVar, Token

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return _request_id_ctx.get()


def set_request_id(rid: str) -> Token:
    return _request_id_ctx.set(rid)


def reset_request_id(token: Token) -> None:
    _request_id_ctx.reset(token)


def ensure_request_id_header(headers: dict[str, str]) -> dict[str, str]:
    rid = get_request_id()
    if rid and "X-Request-ID" not in headers and "x-request-id" not in {k.lower() for k in headers}:
        headers = {**headers, "X-Request-ID": rid}
    return headers


class RequestIdMiddleware(BaseHTTPMiddleware):
    """从网关传入的 X-Request-ID 透传；缺失则生成；写入响应头并进入 contextvar。"""

    header_name = "X-Request-ID"

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get(self.header_name.lower()) or request.headers.get(
            self.header_name
        )
        rid = incoming or str(uuid.uuid4())
        request.state.request_id = rid
        token = set_request_id(rid)
        try:
            response = await call_next(request)
            response.headers[self.header_name] = rid
            return response
        finally:
            reset_request_id(token)
