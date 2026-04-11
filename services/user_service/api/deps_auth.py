from fastapi import Header, HTTPException

from services.user_service.core.exceptions import AuthError
from services.user_service.core.jwt_tokens import verify_token


async def require_bearer_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization[7:].strip()
    try:
        return verify_token(token)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=e.msg) from e
