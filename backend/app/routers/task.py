"""
API 层 —— Celery 任务路由
职责：投递旧版 basic 任务、查询标准化状态、拉取结果；支持批量拉取以降低前端轮询压力。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from redis import Redis
from sqlalchemy.orm import Session

from backend.app.routers.deps import get_current_user
from backend.core.deps import get_db, get_redis
from backend.model.models import User
from backend.app.schemas.common import ApiResponse, success_for_request
from backend.app.schemas.task import (
    TaskBatchData,
    TaskEnqueueData,
    TaskResultData,
    TaskStatusData,
)
from backend.app.services import task_service

router = APIRouter(prefix="/task", tags=["task"])


class TaskBatchIn(BaseModel):
    task_ids: list[str] = Field(default_factory=list, max_length=64)


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
    redis: Annotated[Redis, Depends(get_redis)],
    db: Session = Depends(get_db),
):
    data = task_service.get_task_result(db, task_id, current_user, redis=redis)
    return success_for_request(request, data)


@router.post("/batch", response_model=ApiResponse[TaskBatchData])
def task_batch(
    request: Request,
    body: TaskBatchIn,
    current_user: Annotated[User, Depends(get_current_user)],
    redis: Annotated[Redis, Depends(get_redis)],
    db: Session = Depends(get_db),
):
    """批量获取多个任务的状态与结果；替代 N × (status + result) 轮询风暴。"""
    data = task_service.get_tasks_batch(db, current_user, body.task_ids, redis=redis)
    return success_for_request(request, data)


@router.get("/batch", response_model=ApiResponse[TaskBatchData])
def task_batch_via_query(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    redis: Annotated[Redis, Depends(get_redis)],
    ids: Annotated[str, Query(description="逗号分隔 task_id，最多 64 个")] = "",
    db: Session = Depends(get_db),
):
    """GET /task/batch?ids=a,b,c —— 便于前端 URL 轮询。"""
    task_ids = [x.strip() for x in (ids or "").split(",") if x and x.strip()]
    data = task_service.get_tasks_batch(db, current_user, task_ids, redis=redis)
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
