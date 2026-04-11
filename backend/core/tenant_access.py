"""
多租户文件访问：普通用户强制 WHERE user_id = 当前用户；admin 可跨租户但同名多行时拒绝歧义。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.core.exceptions import ServiceError
from backend.model.models import File, User
from backend.repository import file_repo


def is_admin(user: User) -> bool:
    return (user.role or "").strip().lower() == "admin"


def resolve_file_for_read(db: Session, user: User, filename: str) -> File:
    """解析当前请求可读的一条 File 行（ORM 参数绑定，无字符串拼接 SQL）。"""
    if is_admin(user):
        rows = file_repo.list_files_by_filename_all_tenants(db, filename)
        if not rows:
            raise ServiceError("file not found")
        if len(rows) > 1:
            raise ServiceError("ambiguous filename for admin; use file id")
        return rows[0]
    row = file_repo.get_file_for_tenant(db, filename, user.id)
    if row is None:
        raise ServiceError("file not found")
    return row
