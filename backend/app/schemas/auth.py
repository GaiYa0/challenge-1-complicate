"""登录请求 / Token 载荷展示（OpenAPI）。"""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class TokenData(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserProfile(BaseModel):
    """当前登录用户（与前端 RBAC / 多租户展示对齐；tenant_id 可与库表扩展后对接）。"""

    id: int
    name: str
    role: str = Field(description="admin / user 等，与 JWT 内 role 一致")
    tenant_id: str = Field(default="default", description="租户 ID，请求头 X-Tenant-ID 携带")


class UserListItem(BaseModel):
    """管理员用户列表。"""

    id: int
    username: str
    role: str
    created_at: str | None = None
