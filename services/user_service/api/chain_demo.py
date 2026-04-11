"""
演示：user-service → file-service（HTTP），带 request_id 透传、超时、重试与熔断降级。
"""

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from services.common.circuit import AsyncCircuitBreaker, CircuitOpenError
from services.common.http_resilient import AsyncResilientHttpClient
from services.user_service.api.deps_auth import require_bearer_user
from services.user_service.core.config import get_settings

_log = logging.getLogger("user.chain")

router = APIRouter(prefix="/v1/chain", tags=["chain-demo"])

_file_breaker = AsyncCircuitBreaker(fail_max=5, reset_timeout_s=30.0)
_file_breaker_client = AsyncResilientHttpClient(
    timeout_s=5.0,
    connect_timeout_s=2.0,
    max_attempts=3,
    breaker=_file_breaker,
)


@router.get("/file-health")
async def chain_to_file_health(_claims: dict = Depends(require_bearer_user)):
    base = get_settings().FILE_SERVICE_URL.rstrip("/")
    url = f"{base}/health"
    client = _file_breaker_client
    try:
        resp = await client.request("GET", url)
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
        return {"upstream": "file-service", "status": resp.status_code, "body": body}
    except CircuitOpenError:
        _log.warning("file_circuit_open")
        return JSONResponse(
            status_code=503,
            content={"degraded": True, "reason": "file_service_circuit_open"},
        )
