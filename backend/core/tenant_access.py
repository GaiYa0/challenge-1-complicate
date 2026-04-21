"""
多租户文件访问：普通用户强制 WHERE user_id = 当前用户；admin 可跨租户但同名多行时拒绝歧义。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.core.exceptions import ServiceError
from backend.model.models import File, User
from backend.app.repositories import file_repo


def is_admin(user: User) -> bool:
    return (user.role or "").strip().lower() == "admin"


def resolve_file_for_read(db: Session, user: User, filename: str, *, dataset: str | None = None) -> File:
    """解析当前请求可读的一条 File 行（ORM 参数绑定，无字符串拼接 SQL）。"""
    if is_admin(user):
        rows = file_repo.list_files_by_filename_all_tenants(db, filename)
        if dataset:
            scoped = [r for r in rows if r.dataset == dataset]
            if scoped:
                rows = scoped
        if not rows:
            raise ServiceError("file not found")
        if len(rows) == 1:
            return rows[0]
        own = [r for r in rows if r.user_id == user.id]
        if len(own) == 1:
            return own[0]
        if own:
            own.sort(key=lambda r: r.created_at or "", reverse=True)
            return own[0]
        rows.sort(key=lambda r: r.created_at or "", reverse=True)
        return rows[0]
    row = file_repo.get_file_for_tenant(db, filename, user.id)
    if row is None:
        raise ServiceError("file not found")
    return row
