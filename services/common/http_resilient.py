from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from services.common.circuit import AsyncCircuitBreaker, CircuitOpenError
from services.common.tracing import ensure_request_id_header

_log = logging.getLogger("http.resilient")


def _should_retry_status(code: int) -> bool:
    return code in (502, 503, 504)


class AsyncResilientHttpClient:
    """
    HTTP 调用规范：
    - 必须 timeout
    - 连接失败 / 读超时 / 特定 5xx 自动重试
    - 可选熔断：CircuitOpenError 时由上层返回降级
    """

    def __init__(
        self,
        *,
        timeout_s: float = 5.0,
        connect_timeout_s: float = 2.0,
        max_attempts: int = 3,
        breaker: AsyncCircuitBreaker | None = None,
    ):
        self._timeout = httpx.Timeout(timeout_s, connect=connect_timeout_s)
        self._max_attempts = max_attempts
        self._breaker = breaker

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        headers = kwargs.pop("headers", {}) or {}
        headers = {str(k): str(v) for k, v in headers.items()}
        headers = ensure_request_id_header(headers)

        async def _do_request() -> httpx.Response:
            delay = 0.15
            last_exc: Exception | None = None
            for attempt in range(self._max_attempts):
                try:
                    async with httpx.AsyncClient(timeout=self._timeout) as client:
                        resp = await client.request(method, url, headers=headers, **kwargs)
                    if _should_retry_status(resp.status_code) and attempt < self._max_attempts - 1:
                        _log.warning(
                            "http_retry status=%s attempt=%s url=%s",
                            resp.status_code,
                            attempt + 1,
                            url,
                        )
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, 1.5)
                        continue
                    return resp
                except (httpx.ConnectError, httpx.TimeoutException) as e:
                    last_exc = e
                    if attempt < self._max_attempts - 1:
                        _log.warning(
                            "http_retry exc=%s attempt=%s url=%s",
                            type(e).__name__,
                            attempt + 1,
                            url,
                        )
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, 1.5)
                        continue
                    raise
            assert last_exc is not None
            raise last_exc

        if self._breaker is None:
            return await _do_request()

        try:
            return await self._breaker.call(_do_request)
        except CircuitOpenError:
            _log.warning("circuit_open url=%s method=%s", url, method)
            raise


def sync_request_with_retry(
    method: str,
    url: str,
    *,
    timeout_s: float = 5.0,
    headers: dict[str, str] | None = None,
    json_body: Any | None = None,
    max_attempts: int = 3,
) -> httpx.Response:
    """Celery 等非 async 场景：timeout + 简单重试。"""
    import time

    headers = ensure_request_id_header(dict(headers or {}))
    delay = 0.15
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            with httpx.Client(timeout=timeout_s) as client:
                resp = client.request(method, url, headers=headers, json=json_body)
            if _should_retry_status(resp.status_code) and attempt < max_attempts - 1:
                time.sleep(delay)
                delay = min(delay * 2, 1.5)
                continue
            return resp
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            last_exc = e
            if attempt < max_attempts - 1:
                time.sleep(delay)
                delay = min(delay * 2, 1.5)
                continue
            raise
    assert last_exc is not None
    raise last_exc
