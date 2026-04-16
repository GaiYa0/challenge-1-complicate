"""
审计日志：查询、导出等行为的统一写入。
X-Forwarded-For 仅在对端属于 TRUSTED_PROXY_IPS 时被采信，防止伪造。
"""

from __future__ import annotations

from ipaddress import ip_address, ip_network
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.model.models import User
from backend.app.repositories import audit_repo


def _trusted_proxy_networks() -> list:
    raw = getattr(get_settings(), "TRUSTED_PROXY_IPS", "") or ""
    nets = []
    for item in str(raw).split(","):
        s = item.strip()
        if not s:
            continue
        try:
            nets.append(ip_network(s, strict=False))
        except ValueError:
            continue
    return nets


def _peer_is_trusted(request: Request) -> bool:
    if not request.client:
        return False
    try:
        peer = ip_address(request.client.host)
    except ValueError:
        return False
    for net in _trusted_proxy_networks():
        if peer in net:
            return True
    return False


def client_ip(request: Request) -> str | None:
    if _peer_is_trusted(request):
        xff = request.headers.get("x-forwarded-for")
        if xff:
            first = xff.split(",")[0].strip()
            try:
                ip_address(first)
                return first[:64]
            except ValueError:
                pass
    if request.client:
        return request.client.host[:64]
    return None


def user_agent(request: Request) -> str | None:
    ua = request.headers.get("user-agent")
    return ua[:512] if ua else None


def record(
    db: Session,
    request: Request,
    user: User | None,
    *,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    case_id: int | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    audit_repo.insert(
        db,
        user_id=user.id if user else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        case_id=case_id,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        detail=detail,
    )
