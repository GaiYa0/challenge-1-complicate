"""
报告导出：异步 Celery 生成 PDF/Word，写入 MinIO，返回预签名 URL。
"""

from typing import Annotated

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, Request
from neo4j import Driver
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.routers.deps import get_current_user
from backend.core.config import get_settings
from backend.core.deps import get_db, get_neo4j_driver
from backend.core.exceptions import AppError
from backend.core.tenant_access import is_admin
from backend.model.celery_task_run import CeleryTaskRun
from backend.model.models import User
from backend.app.repositories import case_repo, export_request_repo
from backend.app.schemas.common import ApiResponse, success_for_request
from backend.app.schemas.reports import ReportGenerateIn, ReportTaskQueued, ReportTaskResultOut
from backend.app.services import audit_service, graph_service
from backend.tasks.celery_app import celery_app
from backend.tasks.report_export_task import report_generate_task

router = APIRouter(prefix="/reports", tags=["reports"])


def _ensure_case_access(db: Session, user: User, case_id: int):
    row = case_repo.get_by_id(db, case_id)
    if row is None:
        raise AppError("案件不存在", code=42001, status_code=404)
    if not is_admin(user) and row.user_id != user.id:
        raise AppError("无权访问该案件", code=42002, status_code=403)
    return row


def _verify_report_task_ownership(db: Session, task_id: str, user: User) -> None:
    """fail-closed：未登记的任务一律拒绝。"""
    if is_admin(user):
        return
    row = db.execute(
        select(CeleryTaskRun).where(CeleryTaskRun.celery_task_id == task_id).limit(1)
    ).scalar_one_or_none()
    if row is None:
        raise AppError("任务不存在", code=40401, status_code=404)
    if row.user_id is None or int(row.user_id) != int(user.id):
        raise AppError("无权访问该任务", code=40301, status_code=403)


@router.post("/generate", response_model=ApiResponse[ReportTaskQueued])
def generate_report(
    request: Request,
    body: ReportGenerateIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    neo4j_driver: Annotated[Driver, Depends(get_neo4j_driver)],
):
    """
    投递异步任务生成报告；使用 GET /reports/tasks/{task_id} 轮询结果。
    合规：非 admin 且 COMPLIANCE_EXPORT_APPROVAL_REQUIRED 时须已审批的 export_request_id。
    """
    case_row = _ensure_case_access(db, current_user, body.case_id)
    tid = int(case_row.user_id)
    settings = get_settings()
    if settings.COMPLIANCE_EXPORT_APPROVAL_REQUIRED and not is_admin(current_user):
        if body.export_request_id is None:
            raise AppError(
                "请先提交导出申请并经管理员审批后，再提供 export_request_id",
                code=40302,
                status_code=403,
            )
        er = export_request_repo.get_by_id(db, body.export_request_id)
        if er is None:
            raise AppError("导出申请不存在", code=40401, status_code=404)
        if er.applicant_id != current_user.id:
            raise AppError("无权使用此导出申请", code=40301, status_code=403)
        if (
            er.case_id != body.case_id
            or er.person_id != body.person_id
            or er.file_format != body.format
        ):
            raise AppError("导出申请与报告参数不一致", code=40001, status_code=400)
        if er.status != "approved":
            raise AppError("导出申请未通过审批", code=40303, status_code=403)

    if not graph_service.person_name_exists(neo4j_driver, name=body.person_id, tenant_id=tid):
        raise AppError(
            "人物不在图谱中或 person_id 与 Neo4j 不一致",
            code=40401,
            status_code=404,
        )

    async_result = report_generate_task.delay(
        tid,
        body.case_id,
        body.person_id,
        body.format,
    )
    try:
        db.add(
            CeleryTaskRun(
                celery_task_id=async_result.id,
                user_id=int(current_user.id),
                task_name="report_generate",
                state="PENDING",
            )
        )
        db.flush()
    except Exception:
        db.rollback()
        raise AppError("任务登记失败", code=50001, status_code=500)

    audit_service.record(
        db,
        request,
        current_user,
        action="export_generate",
        resource_type="report_task",
        resource_id=async_result.id,
        case_id=body.case_id,
        detail={
            "person_id": body.person_id,
            "format": body.format,
            "export_request_id": body.export_request_id,
            "approval_enforced": bool(
                settings.COMPLIANCE_EXPORT_APPROVAL_REQUIRED and not is_admin(current_user)
            ),
        },
    )
    db.commit()
    poll = f"/reports/tasks/{async_result.id}"
    return success_for_request(
        request,
        ReportTaskQueued(task_id=async_result.id, status="PENDING", poll_url=poll),
    )


@router.get("/tasks/{task_id}", response_model=ApiResponse[ReportTaskResultOut])
def get_report_task(
    request: Request,
    task_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """查询 Celery 任务状态；SUCCESS 时 result.data 含 download_url。"""
    _verify_report_task_ownership(db, task_id, current_user)
    ar = AsyncResult(task_id, app=celery_app)
    if ar.state == "PENDING":
        return success_for_request(
            request,
            ReportTaskResultOut(task_id=task_id, status="PENDING", result=None, error=None),
        )
    if ar.state == "SUCCESS":
        payload = ar.result
        if isinstance(payload, dict) and payload.get("code") == 0:
            return success_for_request(
                request,
                ReportTaskResultOut(
                    task_id=task_id, status="SUCCESS", result=payload.get("data")
                ),
            )
        return success_for_request(
            request,
            ReportTaskResultOut(
                task_id=task_id,
                status="FAILURE",
                result=None,
                error=str(payload),
            ),
        )
    if ar.state == "FAILURE":
        err = str(ar.result) if ar.result else "task failed"
        return success_for_request(
            request,
            ReportTaskResultOut(task_id=task_id, status="FAILURE", result=None, error=err),
        )
    return success_for_request(
        request,
        ReportTaskResultOut(task_id=task_id, status=ar.state, result=None, error=None),
    )
