"""
除白名单路径外，要求请求携带合法 Bearer JWT（仅签名校验，不落库；路由内 get_current_user 再校验 DB）。
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from backend.core.exceptions import AuthError
from backend.core.jwt_tokens import verify_token
from backend.core.response import error, request_id_from
from backend.core.security_audit import log_security_event


def is_public_path(path: str) -> bool:
    p = path.split("?", 1)[0].rstrip("/") or "/"
    if p == "/auth/login":
        return True
    if p in (
        "/docs",
        "/openapi.json",
        "/redoc",
        "/metrics",
        "/live",
        "/ready",
        "/ready/deep",
        "/ws",
    ):
        return True
    if p.startswith("/docs/") or p.startswith("/redoc"):
        return True
    return False


def _bearer_token(request: Request) -> str | None:
    h = request.headers.get("authorization")
    if not h:
        return None
    parts = h.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    t = parts[1].strip()
    return t or None


async def jwt_gate_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)
    path = request.url.path
    if is_public_path(path):
        return await call_next(request)

    token = _bearer_token(request)
    rid = request_id_from(request)
    if not token:
        log_security_event("abnormal_access", reason="missing_bearer", path=path)
        body = error(40101, "missing authorization", rid).model_dump(mode="json")
        return JSONResponse(status_code=401, content=body)
    try:
        payload = verify_token(token)
        uid = int(payload["user_id"])
    except AuthError as e:
        log_security_event("abnormal_access", reason="invalid_token", path=path, detail=e.msg)
        body = error(e.code, e.msg, rid).model_dump(mode="json")
        return JSONResponse(status_code=401, content=body)
    except (KeyError, TypeError, ValueError) as e:
        log_security_event("abnormal_access", reason="bad_token_payload", path=path)
        body = error(40101, "invalid token payload", rid).model_dump(mode="json")
        return JSONResponse(status_code=401, content=body)

    request.state.jwt_user_id = uid
    return await call_next(request)
