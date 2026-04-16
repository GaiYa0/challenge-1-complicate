from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.model.audit_log import AuditLog


def insert(
    db: Session,
    *,
    user_id: int | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    case_id: int | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditLog:
    row = AuditLog(
        user_id=user_id,
        case_id=case_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        detail=detail,
    )
    db.add(row)
    db.flush()
    return row


def list_logs(
    db: Session,
    *,
    limit: int = 200,
    user_id: int | None = None,
    case_id: int | None = None,
    action_prefix: str | None = None,
) -> list[AuditLog]:
    q = db.query(AuditLog).order_by(AuditLog.created_at.desc())
    if user_id is not None:
        q = q.filter(AuditLog.user_id == user_id)
    if case_id is not None:
        q = q.filter(AuditLog.case_id == case_id)
    if action_prefix:
        q = q.filter(AuditLog.action.startswith(action_prefix))
    return q.limit(limit).all()
