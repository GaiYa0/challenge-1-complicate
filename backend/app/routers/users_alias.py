"""
`/users`、`/tasks/active` 等**对外命名别名**，补齐前端历史路径。

- 前端曾调用 `GET /api/users`、`GET /api/tasks/active` —— 它们历史上挂在
  `/auth/users`、`/task/...` 之下；本路由统一对外暴露复数名称，
  内部委托到现有 service，避免在视图层散落兼容逻辑。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.routers.deps import get_current_user
from backend.app.routers.rbac import require_role
from backend.core.deps import get_db
from backend.model.models import User
from backend.model.celery_task_run import CeleryTaskRun
from backend.app.schemas.auth import UserListItem
from backend.app.schemas.common import ApiResponse, success_for_request
from backend.app.services import auth_service


users_router = APIRouter(tags=["users-alias"])
tasks_router = APIRouter(tags=["tasks-alias"])


@users_router.get("/users", response_model=ApiResponse[list[UserListItem]])
def list_users_plural(
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


@users_router.delete("/users/{user_id}", response_model=ApiResponse[None])
def delete_user_plural(
    request: Request,
    user_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    auth_service.delete_user_as_admin(db, user_id, current_user)
    return success_for_request(request, None, msg="deleted")


@tasks_router.get("/tasks/active", response_model=ApiResponse[dict])
def list_active_tasks(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """返回当前租户尚未进入终态的 Celery 任务（PENDING/STARTED/RETRY）。"""
    uid = int(current_user.id)
    q = (
        select(CeleryTaskRun)
        .where(
            CeleryTaskRun.user_id == uid,
            CeleryTaskRun.state.in_(("PENDING", "STARTED", "RETRY")),
        )
        .order_by(CeleryTaskRun.id.desc())
        .limit(100)
    )
    rows = list(db.execute(q).scalars().all())
    items = [
        {
            "task_id": r.celery_task_id,
            "task_name": r.task_name,
            "state": r.state,
            "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
        }
        for r in rows
    ]
    return success_for_request(request, {"items": items, "count": len(items)})
