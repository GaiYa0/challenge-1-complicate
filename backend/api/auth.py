"""
认证路由：登录签发 JWT（无需 Bearer）。
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.api.rbac import require_role
from backend.core.deps import get_db
from backend.core.response import success_for_request
from backend.model.models import User
from backend.schema.auth import LoginRequest, TokenData, UserListItem, UserProfile
from backend.schema.common import ApiResponse
from backend.service import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=ApiResponse[TokenData])
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    token = auth_service.login(db, body.username, body.password)
    return success_for_request(request, TokenData(access_token=token))


@router.get("/me", response_model=ApiResponse[UserProfile])
def me(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    # 库表扩展 tenant 列后，可改为读取 current_user.tenant_id
    data = UserProfile(
        id=current_user.id,
        name=current_user.username,
        role=current_user.role,
        tenant_id="default",
    )
    return success_for_request(request, data)


@router.get("/users", response_model=ApiResponse[list[UserListItem]])
def list_users_admin(
    request: Request,
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    rows = auth_service.list_users_for_admin(db)
    data = [
        UserListItem(
            id=u.id,
            username=u.username,
            role=u.role,
            created_at=u.created_at.isoformat() if u.created_at else None,
        )
        for u in rows
    ]
    return success_for_request(request, data)


@router.delete("/users/{user_id}", response_model=ApiResponse[None])
def delete_user_admin(
    request: Request,
    user_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    auth_service.delete_user_as_admin(db, user_id, current_user)
    return success_for_request(request, None, msg="deleted")
