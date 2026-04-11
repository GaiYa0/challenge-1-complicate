"""
API 网关：统一入口 /user、/file；JWT 校验；request_id 透传；熔断与重试在代理层实现。

启动（项目根为工作目录，PYTHONPATH=.）：

  uvicorn services.gateway.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from services.common.circuit import AsyncCircuitBreaker
from services.common.http_resilient import AsyncResilientHttpClient
from services.common.logging_setup import configure_logging
from services.common.tracing import RequestIdMiddleware
from services.gateway.api.proxy import build_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging("api-gateway")
    yield


user_breaker = AsyncCircuitBreaker(fail_max=5, reset_timeout_s=30.0)
file_breaker = AsyncCircuitBreaker(fail_max=5, reset_timeout_s=30.0)
user_http = AsyncResilientHttpClient(
    timeout_s=30.0,
    connect_timeout_s=3.0,
    max_attempts=3,
    breaker=user_breaker,
)
file_http = AsyncResilientHttpClient(
    timeout_s=120.0,
    connect_timeout_s=5.0,
    max_attempts=3,
    breaker=file_breaker,
)

app = FastAPI(title="api-gateway", lifespan=lifespan)
app.add_middleware(RequestIdMiddleware)
app.include_router(build_router(user_client=user_http, file_client=file_http))


@app.get("/health")
def gateway_health():
    return {"status": "ok", "service": "api-gateway"}
