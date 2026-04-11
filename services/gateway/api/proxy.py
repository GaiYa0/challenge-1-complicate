from __future__ import annotations

import logging
from urllib.parse import urljoin

import httpx
from fastapi import APIRouter, Request, Response

from services.common.circuit import CircuitOpenError
from services.common.http_resilient import AsyncResilientHttpClient
from services.common.tracing import get_request_id
from services.gateway.auth.jwt_gate import require_bearer_jwt
from services.gateway.core.config import get_gateway_settings, resolve_upstream_urls

_log = logging.getLogger("gateway.proxy")

HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "transfer-encoding",
    "te",
    "trailer",
    "trailers",
    "upgrade",
    "host",
    "content-length",
}


def _filter_headers(request: Request) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in request.headers.items():
        if k.lower() in HOP_BY_HOP:
            continue
        out[k] = v
    rid = get_request_id()
    if rid:
        out["X-Request-ID"] = rid
    return out


def build_router(
    *,
    user_client: AsyncResilientHttpClient,
    file_client: AsyncResilientHttpClient,
) -> APIRouter:
    router = APIRouter()

    @router.api_route("/user/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    async def proxy_user(path: str, request: Request) -> Response:
        require_bearer_jwt(request, get_gateway_settings().JWT_SECRET)
        return await _forward(request, path, resolve_upstream_urls()["user"], user_client)

    @router.api_route("/file/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    async def proxy_file(path: str, request: Request) -> Response:
        require_bearer_jwt(request, get_gateway_settings().JWT_SECRET)
        return await _forward(request, path, resolve_upstream_urls()["file"], file_client)

    return router


async def _forward(
    request: Request,
    path: str,
    upstream_base: str,
    client: AsyncResilientHttpClient,
) -> Response:
    subpath = path or ""
    target: str = urljoin(upstream_base + "/", subpath)
    if request.url.query:
        target = f"{target}?{request.url.query}"
    body = await request.body()
    headers = _filter_headers(request)
    try:
        upstream = await client.request(
            request.method,
            target,
            headers=headers,
            content=body,
        )
    except CircuitOpenError:
        _log.error("circuit_open target=%s", upstream_base)
        rid = get_request_id() or ""
        return Response(
            content=b'{"degraded":true,"reason":"upstream_circuit_open"}',
            status_code=503,
            media_type="application/json",
            headers={"X-Request-ID": rid},
        )
    except httpx.TimeoutException:
        _log.error("upstream_timeout target=%s", upstream_base)
        rid = get_request_id() or ""
        return Response(
            content=b'{"code":50400,"msg":"upstream timeout"}',
            status_code=504,
            media_type="application/json",
            headers={"X-Request-ID": rid},
        )
    except (httpx.ConnectError, httpx.NetworkError) as exc:
        _log.error("upstream_unreachable target=%s err=%s", upstream_base, exc)
        rid = get_request_id() or ""
        return Response(
            content=b'{"code":50200,"msg":"upstream unreachable"}',
            status_code=502,
            media_type="application/json",
            headers={"X-Request-ID": rid},
        )
    out_headers: dict[str, str] = {}
    ct = upstream.headers.get("content-type")
    if ct:
        out_headers["content-type"] = ct
    rid = get_request_id() or ""
    out_headers["X-Request-ID"] = rid
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=out_headers,
    )
