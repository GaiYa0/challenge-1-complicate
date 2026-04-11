from fastapi import Header, HTTPException

from services.user_service.core.config import get_settings


def verify_internal_token(x_internal_token: str | None = Header(default=None)) -> None:
    if not x_internal_token or x_internal_token != get_settings().INTERNAL_API_TOKEN:
        raise HTTPException(status_code=403, detail="invalid internal token")
