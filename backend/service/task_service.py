"""
Service 层 —— Celery 任务管理
职责：投递 analyze / clean / feature 任务；查询状态（标准化状态机）。
"""

import json
import logging
from typing import Any

from celery.result import AsyncResult
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.exceptions import ServiceError
from backend.model.celery_task_run import CeleryTaskRun
from backend.model.models import User
from backend.schema.task import TaskEnqueueData, TaskResultData, TaskStatusData
from backend.service.file_service import file_owner_user_id_if_accessible
from backend.tasks.analyze_task import analyze_data_task
from backend.tasks.celery_app import celery_app
from backend.tasks.clean_task import clean_data_task
from backend.tasks.feature_task import feature_extract_task

_log = logging.getLogger(__name__)


def normalize_task_state(celery_state: str) -> str:
    """映射为 PENDING | STARTED | SUCCESS | FAILURE。"""
    if celery_state == "SUCCESS":
        return "SUCCESS"
    if celery_state == "FAILURE":
        return "FAILURE"
    if celery_state in ("STARTED", "RETRY"):
        return "STARTED"
    return "PENDING"


def enqueue_analyze(db: Session, filename: str, user: User) -> TaskEnqueueData:
    """兼容旧接口：等价于 basic 分析。"""
    owner_id = file_owner_user_id_if_accessible(db, filename, user)
    if owner_id is None:
        raise ServiceError("file not found")
    result = analyze_data_task.delay("basic", filename, owner_id)
    return TaskEnqueueData(task_id=result.id)


def enqueue_clean(db: Session, filename: str, user: User) -> TaskEnqueueData:
    owner_id = file_owner_user_id_if_accessible(db, filename, user)
    if owner_id is None:
        raise ServiceError("file not found")
    result = clean_data_task.delay(filename, owner_id)
    return TaskEnqueueData(task_id=result.id)


def enqueue_feature_extract(db: Session, filename: str, user: User) -> TaskEnqueueData:
    owner_id = file_owner_user_id_if_accessible(db, filename, user)
    if owner_id is None:
        raise ServiceError("file not found")
    result = feature_extract_task.delay(filename, owner_id)
    return TaskEnqueueData(task_id=result.id)


def _verify_task_ownership(db: Session, task_id: str, user: User) -> None:
    """校验任务归属，防止 IDOR。管理员可查看所有任务。"""
    if getattr(user, "role", "") == "admin":
        return
    row = db.execute(
        select(CeleryTaskRun).where(CeleryTaskRun.celery_task_id == task_id).limit(1)
    ).scalar_one_or_none()
    if row is not None and row.user_id is not None and row.user_id != user.id:
        raise ServiceError("task not found")


def get_task_status(db: Session, task_id: str, user: User) -> TaskStatusData:
    _verify_task_ownership(db, task_id, user)
    ar = AsyncResult(task_id, app=celery_app)
    return TaskStatusData(state=normalize_task_state(ar.state))


def get_task_result(db: Session, task_id: str, user: User) -> TaskResultData:
    _verify_task_ownership(db, task_id, user)
    ar = AsyncResult(task_id, app=celery_app)
    st = normalize_task_state(ar.state)
    if ar.successful():
        res = ar.result
        if isinstance(res, dict):
            return TaskResultData(state=st, result=res)
        try:
            return TaskResultData(state=st, result=json.loads(json.dumps(res, default=str)))
        except (TypeError, ValueError):
            return TaskResultData(state=st, result={"raw": str(res)})
    if ar.failed():
        return TaskResultData(state="FAILURE", result={"msg": str(ar.info) if ar.info else "task failed"})
    return TaskResultData(state=st, result={"msg": "任务未完成"})
