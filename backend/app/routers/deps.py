"""
API 层 —— 公共依赖
职责：get_current_user：Bearer JWT → 校验 → DB 用户 → 写入 request.state.user
"""

from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from backend.core.deps import get_db
from backend.core.exceptions import AuthError, ForbiddenError
from backend.core.jwt_tokens import verify_token
from backend.core.security_audit import log_security_event
from backend.model.models import User
from backend.app.repositories import user_repo


def get_current_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> User:
    if not authorization:
        raise AuthError("missing authorization", code=40101)
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthError("invalid authorization header", code=40101)
    token = parts[1].strip()
    if not token:
        raise AuthError("empty token", code=40101)

    payload = verify_token(token)
    try:
        user_id = int(payload["user_id"])
        role = str(payload["role"])
    except (KeyError, TypeError, ValueError) as e:
        raise AuthError("invalid token payload") from e

    user = user_repo.get_user_by_id(db, user_id)
    if user is None:
        log_security_event("abnormal_access", reason="user_not_found_for_token", token_user_id=user_id)
        raise AuthError("user not found", code=40103)
    if user.role != role:
        log_security_event(
            "permission_denied",
            reason="token_role_mismatch",
            user_id=user.id,
            db_role=user.role,
            token_role=role,
        )
        raise ForbiddenError("token role mismatch", code=40301)

    request.state.user = user
    return user
