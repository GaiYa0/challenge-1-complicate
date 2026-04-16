"""
合规与安全：导出审批、审计日志查询。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from backend.app.routers.deps import get_current_user
from backend.core.config import get_settings
from backend.core.deps import get_db
from backend.core.exceptions import AppError
from backend.core.tenant_access import is_admin
from backend.model.audit_log import AuditLog
from backend.model.export_request import ExportRequest
from backend.model.models import User
from backend.app.repositories import case_repo, export_request_repo
from backend.app.schemas.common import ApiResponse, success_for_request
from backend.app.schemas.compliance import (
    AuditLogOut,
    ExportRequestCreate,
    ExportRequestOut,
    ExportReviewBody,
)
from backend.app.services import audit_service

router = APIRouter(prefix="/compliance", tags=["compliance"])


def _to_export_out(row: ExportRequest) -> ExportRequestOut:
    return ExportRequestOut(
        id=row.id,
        applicant_id=row.applicant_id,
        case_id=row.case_id,
        person_id=row.person_id,
        file_format=row.file_format,
        status=row.status,
        reviewer_id=row.reviewer_id,
        review_note=row.review_note,
        reviewed_at=row.reviewed_at.isoformat() if row.reviewed_at else None,
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


def _to_audit_out(row: AuditLog) -> AuditLogOut:
    return AuditLogOut(
        id=row.id,
        user_id=row.user_id,
        case_id=row.case_id,
        action=row.action,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        ip_address=row.ip_address,
        detail=row.detail if isinstance(row.detail, dict) else None,
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


def _ensure_case_owner_or_admin(db: Session, user: User, case_id: int):
    row = case_repo.get_by_id(db, case_id)
    if row is None:
        raise AppError("案件不存在", code=40401, status_code=404)
    if not is_admin(user) and row.user_id != user.id:
        raise AppError("无权访问该案件", code=42002, status_code=403)
    return row


@router.post("/export-requests", response_model=ApiResponse[ExportRequestOut])
def create_export_request(
    request: Request,
    body: ExportRequestCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """用户申请导出报告（待管理员审批）。"""
    _ensure_case_owner_or_admin(db, current_user, body.case_id)
    row = export_request_repo.create(
        db,
        applicant_id=current_user.id,
        case_id=body.case_id,
        person_id=body.person_id,
        file_format=body.file_format,
    )
    audit_service.record(
        db,
        request,
        current_user,
        action="export_request_create",
        resource_type="export_request",
        resource_id=str(row.id),
        case_id=body.case_id,
        detail={"person_id": body.person_id, "file_format": body.file_format},
    )
    return success_for_request(request, _to_export_out(row))


@router.get("/export-requests", response_model=ApiResponse[list[ExportRequestOut]])
def list_export_requests(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    scope: Annotated[str | None, Query(description="mine=本人申请；all=管理员全部")] = "mine",
):
    if scope == "all":
        if not is_admin(current_user):
            raise AppError("需要管理员权限", code=40301, status_code=403)
        rows = export_request_repo.list_all(db)
    else:
        rows = export_request_repo.list_for_user(db, current_user.id)
    return success_for_request(request, [_to_export_out(r) for r in rows])


@router.post(
    "/export-requests/{request_id}/approve",
    response_model=ApiResponse[ExportRequestOut],
)
def approve_export_request(
    request: Request,
    request_id: int,
    body: ExportReviewBody,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    if not is_admin(current_user):
        raise AppError("需要管理员审批权限", code=40301, status_code=403)
    row = export_request_repo.get_by_id(db, request_id)
    if row is None:
        raise AppError("申请不存在", code=40401, status_code=404)
    if row.status != "pending":
        raise AppError("申请状态不可审批", code=40001, status_code=400)
    row = export_request_repo.set_status(
        db,
        row,
        status="approved",
        reviewer_id=current_user.id,
        review_note=body.note,
    )
    audit_service.record(
        db,
        request,
        current_user,
        action="export_request_approve",
        resource_type="export_request",
        resource_id=str(row.id),
        case_id=row.case_id,
        detail={"applicant_id": row.applicant_id},
    )
    return success_for_request(request, _to_export_out(row))


@router.post(
    "/export-requests/{request_id}/reject",
    response_model=ApiResponse[ExportRequestOut],
)
def reject_export_request(
    request: Request,
    request_id: int,
    body: ExportReviewBody,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    if not is_admin(current_user):
        raise AppError("需要管理员审批权限", code=40301, status_code=403)
    row = export_request_repo.get_by_id(db, request_id)
    if row is None:
        raise AppError("申请不存在", code=40401, status_code=404)
    if row.status != "pending":
        raise AppError("申请状态不可审批", code=40001, status_code=400)
    row = export_request_repo.set_status(
        db,
        row,
        status="rejected",
        reviewer_id=current_user.id,
        review_note=body.note,
    )
    audit_service.record(
        db,
        request,
        current_user,
        action="export_request_reject",
        resource_type="export_request",
        resource_id=str(row.id),
        case_id=row.case_id,
        detail={"applicant_id": row.applicant_id},
    )
    return success_for_request(request, _to_export_out(row))


@router.get("/audit-logs", response_model=ApiResponse[list[AuditLogOut]])
def list_audit_logs(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    user_id: Annotated[int | None, Query()] = None,
    case_id: Annotated[int | None, Query()] = None,
    action_prefix: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
):
    """审计日志（管理员可查全局；普通用户仅能查本人 user_id）。"""
    from backend.app.repositories import audit_repo

    uid_filter = user_id if is_admin(current_user) else current_user.id
    rows = audit_repo.list_logs(
        db,
        limit=limit,
        user_id=uid_filter,
        case_id=case_id,
        action_prefix=action_prefix,
    )
    return success_for_request(request, [_to_audit_out(r) for r in rows])


@router.get("/settings", response_model=ApiResponse[dict])
def compliance_settings(request: Request):
    """脱敏规则说明与导出策略开关（无需敏感权限）。"""
    s = get_settings()
    return success_for_request(
        request,
        {
            "export_approval_required": s.COMPLIANCE_EXPORT_APPROVAL_REQUIRED,
            "masking": {
                "phone": "保留前3后4，中间****",
                "bank_card": "仅保留后4位，前缀****",
            },
        },
    )
