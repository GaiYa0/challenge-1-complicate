"""
API 层 —— Celery 任务路由
职责：投递旧版 basic 任务、查询标准化状态、拉取结果。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.core.deps import get_db
from backend.model.models import User
from backend.schema.common import ApiResponse, success_for_request
from backend.schema.task import TaskEnqueueData, TaskResultData, TaskStatusData
from backend.service import task_service

router = APIRouter(prefix="/task", tags=["task"])


@router.post("/analyze/{filename}", response_model=ApiResponse[TaskEnqueueData])
def task_enqueue_analyze(
    request: Request,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    data = task_service.enqueue_analyze(db, filename, current_user)
    return success_for_request(request, data)


@router.get("/result/{task_id}", response_model=ApiResponse[TaskResultData])
def task_result(
    request: Request,
    task_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    data = task_service.get_task_result(db, task_id, current_user)
    return success_for_request(request, data)


@router.get("/{task_id}", response_model=ApiResponse[TaskStatusData])
def get_task_status_by_id(
    request: Request,
    task_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """GET /task/{task_id} → PENDING | STARTED | SUCCESS | FAILURE"""
    data = task_service.get_task_status(db, task_id, current_user)
    return success_for_request(request, data)
