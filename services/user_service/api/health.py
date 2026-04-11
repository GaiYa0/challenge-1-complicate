from fastapi import APIRouter

from services.common.tracing import get_request_id

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok", "service": "user-service", "request_id": get_request_id()}
