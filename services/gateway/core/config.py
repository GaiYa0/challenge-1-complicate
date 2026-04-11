from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.gateway", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "api-gateway"
    JWT_SECRET: str = Field(default="change-me-in-production", description="须与 user-service 一致")
    REGISTRY_PATH: str = Field(
        default="services/gateway/config/registry.yaml",
        description="相对工作目录的服务注册表",
    )
    USER_SERVICE_URL: str | None = None
    FILE_SERVICE_URL: str | None = None


@lru_cache
def get_gateway_settings() -> GatewaySettings:
    return GatewaySettings()


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def resolve_upstream_urls() -> dict[str, str]:
    s = get_gateway_settings()
    data = _load_yaml(Path(s.REGISTRY_PATH))
    routes = (data.get("routes") or {}) if isinstance(data, dict) else {}
    user_default = ((routes.get("user") or {}) if isinstance(routes, dict) else {}).get("base_url")
    file_default = ((routes.get("file") or {}) if isinstance(routes, dict) else {}).get("base_url")
    user = (s.USER_SERVICE_URL or user_default or "http://127.0.0.1:8001").rstrip("/")
    file_ = (s.FILE_SERVICE_URL or file_default or "http://127.0.0.1:8002").rstrip("/")
    return {"user": user, "file": file_}
