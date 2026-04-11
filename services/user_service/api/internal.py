"""
服务间 HTTP 接口：仅携带 X-Internal-Token 的其他微服务可调用。
禁止其他服务直连 user_db。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from services.user_service.api.deps_internal import verify_internal_token
from services.user_service.core.database import get_db
from services.user_service.core.exceptions import AuthError
from services.user_service.core.jwt_tokens import verify_token
from services.user_service.schema.auth import TokenValidateRequest, TokenValidateResponse, UserPublic
from services.user_service.service import user_service

router = APIRouter(prefix="/internal/v1", tags=["internal"], dependencies=[Depends(verify_internal_token)])


@router.get("/users/{user_id}", response_model=UserPublic)
def internal_get_user(user_id: int, db: Session = Depends(get_db)):
    u = user_service.get_user_public(db, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="user not found")
    return u


@router.post("/token/validate", response_model=TokenValidateResponse)
def internal_validate_token(body: TokenValidateRequest, db: Session = Depends(get_db)):
    try:
        payload = verify_token(body.token)
        uid = int(payload["user_id"])
    except (AuthError, KeyError, TypeError, ValueError):
        return TokenValidateResponse(valid=False, reason="invalid_token")

    u = user_service.get_user_public(db, uid)
    if u is None:
        return TokenValidateResponse(valid=False, reason="user_not_found")
    if u.role != str(payload.get("role", "")):
        return TokenValidateResponse(valid=False, reason="role_mismatch")
    return TokenValidateResponse(valid=True, user_id=u.id, username=u.username, role=u.role)
