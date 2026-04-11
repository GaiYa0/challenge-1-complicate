"""
RBAC：基于 JWT 已解析用户角色，限制接口访问。

用法：
    @router.post("/admin-only")
    def x(_: User = Depends(require_role("admin"))):
        ...
"""

from collections.abc import Callable

from fastapi import Depends

from backend.api.deps import get_current_user
from backend.core.exceptions import ForbiddenError
from backend.core.security_audit import log_security_event
from backend.model.models import User


def require_role(*allowed_roles: str) -> Callable[..., User]:
    """仅允许指定角色（小写比较）；否则 403 + 安全日志。"""
    allowed = {r.strip().lower() for r in allowed_roles if r}

    def dependency(user: User = Depends(get_current_user)) -> User:
        role = (user.role or "user").strip().lower()
        if role not in allowed:
            log_security_event(
                "permission_denied",
                user_id=user.id,
                role=role,
                required_roles=list(allowed_roles),
            )
            raise ForbiddenError("insufficient role", code=40302)
        return user

    return dependency
