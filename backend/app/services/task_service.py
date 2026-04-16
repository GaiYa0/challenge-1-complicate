"""
Service 层 —— Celery 任务管理
职责：投递 analyze / clean / feature 任务；查询状态（标准化状态机）。严格 fail-closed。
"""

import json
import logging
from typing import Any

from celery.result import AsyncResult
from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.exceptions import ServiceError
from backend.model.celery_task_run import CeleryTaskRun
from backend.model.models import User
from backend.app.schemas.task import (
    TaskBatchData,
    TaskBatchItem,
    TaskEnqueueData,
    TaskResultData,
    TaskStatusData,
)
from backend.app.services.file_service import file_owner_user_id_if_accessible
from backend.tasks.analyze_task import analyze_data_task
from backend.tasks.celery_app import celery_app
from backend.tasks.clean_task import clean_data_task
from backend.tasks.feature_task import feature_extract_task

_log = logging.getLogger(__name__)


def normalize_task_state(celery_state: str) -> str:
    if celery_state == "SUCCESS":
        return "SUCCESS"
    if celery_state == "FAILURE":
        return "FAILURE"
    if celery_state in ("STARTED", "RETRY"):
        return "STARTED"
    return "PENDING"


def _record_task(
    db: Session,
    *,
    task_id: str,
    task_name: str,
    user_id: int,
) -> None:
    """登记 Celery 任务归属，fail-closed 依赖此记录。"""
    try:
        db.add(
            CeleryTaskRun(
                celery_task_id=task_id,
                user_id=int(user_id),
                task_name=task_name,
                state="PENDING",
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        raise ServiceError("failed to record task")


def enqueue_analyze(db: Session, filename: str, user: User) -> TaskEnqueueData:
    owner_id = file_owner_user_id_if_accessible(db, filename, user)
    if owner_id is None:
        raise ServiceError("file not found")
    result = analyze_data_task.delay("basic", filename, owner_id)
    _record_task(db, task_id=result.id, task_name="analyze_data", user_id=user.id)
    return TaskEnqueueData(task_id=result.id)


def enqueue_clean(db: Session, filename: str, user: User) -> TaskEnqueueData:
    owner_id = file_owner_user_id_if_accessible(db, filename, user)
    if owner_id is None:
        raise ServiceError("file not found")
    result = clean_data_task.delay(filename, owner_id)
    _record_task(db, task_id=result.id, task_name="clean_data", user_id=user.id)
    return TaskEnqueueData(task_id=result.id)


def enqueue_feature_extract(db: Session, filename: str, user: User) -> TaskEnqueueData:
    owner_id = file_owner_user_id_if_accessible(db, filename, user)
    if owner_id is None:
        raise ServiceError("file not found")
    result = feature_extract_task.delay(filename, owner_id)
    _record_task(db, task_id=result.id, task_name="feature_extract", user_id=user.id)
    return TaskEnqueueData(task_id=result.id)


def _verify_task_ownership(db: Session, task_id: str, user: User) -> None:
    """fail-closed：未登记或归属不符一律拒绝；admin 放行。"""
    if getattr(user, "role", "") == "admin":
        return
    row = db.execute(
        select(CeleryTaskRun).where(CeleryTaskRun.celery_task_id == task_id).limit(1)
    ).scalar_one_or_none()
    if row is None:
        raise ServiceError("task not found")
    if row.user_id is None or int(row.user_id) != int(user.id):
        raise ServiceError("task not found")


def get_task_status(db: Session, task_id: str, user: User) -> TaskStatusData:
    _verify_task_ownership(db, task_id, user)
    ar = AsyncResult(task_id, app=celery_app)
    return TaskStatusData(state=normalize_task_state(ar.state))


def get_task_result(
    db: Session, task_id: str, user: User, *, redis: Redis | None = None
) -> TaskResultData:
    _verify_task_ownership(db, task_id, user)
    cache_key = f"task:result:{task_id}:{int(user.id)}"
    if redis is not None:
        try:
            raw = redis.get(cache_key)
        except Exception:
            raw = None
            _log.debug("task_result_cache_get_failed", exc_info=True)
        if raw is not None:
            try:
                return TaskResultData.model_validate(json.loads(raw))
            except (json.JSONDecodeError, TypeError, ValueError):
                try:
                    redis.delete(cache_key)
                except Exception:
                    pass
    ar = AsyncResult(task_id, app=celery_app)
    st = normalize_task_state(ar.state)
    if ar.successful():
        res = ar.result
        if isinstance(res, dict):
            out = TaskResultData(state=st, result=res)
        else:
            try:
                out = TaskResultData(
                    state=st, result=json.loads(json.dumps(res, default=str))
                )
            except (TypeError, ValueError):
                out = TaskResultData(state=st, result={"raw": str(res)})
        if redis is not None and st == "SUCCESS":
            try:
                redis.setex(
                    cache_key,
                    120,
                    json.dumps(out.model_dump(mode="json"), default=str),
                )
            except Exception:
                _log.debug("task_result_cache_set_failed", exc_info=True)
        return out
    if ar.failed():
        return TaskResultData(
            state="FAILURE",
            result={"msg": str(ar.info) if ar.info else "task failed"},
        )
    return TaskResultData(state=st, result={"msg": "任务未完成"})


def _owned_task_ids(db: Session, user: User, task_ids: list[str]) -> set[str]:
    """admin 放行全部；否则返回 user 真正拥有的子集。"""
    cleaned: list[str] = []
    for t in task_ids or []:
        if isinstance(t, str):
            v = t.strip()
            if v:
                cleaned.append(v)
    if not cleaned:
        return set()
    if getattr(user, "role", "") == "admin":
        return set(cleaned)
    rows = db.execute(
        select(CeleryTaskRun.celery_task_id, CeleryTaskRun.user_id).where(
            CeleryTaskRun.celery_task_id.in_(cleaned)
        )
    ).all()
    owned: set[str] = set()
    for rid, rowner in rows:
        if rowner is not None and int(rowner) == int(user.id):
            owned.add(str(rid))
    return owned


def _batch_result_cache_key(task_id: str, user_id: int) -> str:
    return f"task:result:{task_id}:{int(user_id)}"


def _build_batch_item(
    task_id: str, *, redis: Redis | None, user_id: int
) -> TaskBatchItem:
    if redis is not None:
        try:
            raw = redis.get(_batch_result_cache_key(task_id, user_id))
        except Exception:
            raw = None
        if raw is not None:
            try:
                cached = json.loads(raw)
                return TaskBatchItem(
                    task_id=task_id,
                    state=str(cached.get("state", "SUCCESS")),
                    result=cached.get("result"),
                )
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
    try:
        ar = AsyncResult(task_id, app=celery_app)
        st = normalize_task_state(ar.state)
    except Exception as e:
        return TaskBatchItem(task_id=task_id, state="PENDING", error=str(e))

    if ar.successful():
        res = ar.result
        payload: Any
        if isinstance(res, dict):
            payload = res
        else:
            try:
                payload = json.loads(json.dumps(res, default=str))
            except (TypeError, ValueError):
                payload = {"raw": str(res)}
        if redis is not None:
            try:
                redis.setex(
                    _batch_result_cache_key(task_id, user_id),
                    120,
                    json.dumps({"state": st, "result": payload}, default=str),
                )
            except Exception:
                _log.debug("task_result_cache_set_failed", exc_info=True)
        return TaskBatchItem(task_id=task_id, state=st, result=payload)

    if ar.failed():
        return TaskBatchItem(
            task_id=task_id,
            state="FAILURE",
            error=str(ar.info) if ar.info else "task failed",
        )
    return TaskBatchItem(task_id=task_id, state=st)


def get_tasks_batch(
    db: Session,
    user: User,
    task_ids: list[str],
    *,
    redis: Redis | None = None,
    max_ids: int = 64,
) -> TaskBatchData:
    """一次拉多任务；未授权/未登记的 id 仅返回 UNAUTHORIZED 占位，避免放大查询。"""
    if not task_ids:
        return TaskBatchData(items=[])
    unique_ids: list[str] = []
    seen: set[str] = set()
    for tid in task_ids:
        if isinstance(tid, str):
            v = tid.strip()
            if v and v not in seen:
                seen.add(v)
                unique_ids.append(v)
        if len(unique_ids) >= int(max_ids):
            break
    if not unique_ids:
        return TaskBatchData(items=[])

    owned = _owned_task_ids(db, user, unique_ids)
    items: list[TaskBatchItem] = []
    for tid in unique_ids:
        if tid not in owned:
            items.append(
                TaskBatchItem(task_id=tid, state="UNAUTHORIZED", error="task not found")
            )
            continue
        items.append(_build_batch_item(tid, redis=redis, user_id=int(user.id)))
    return TaskBatchData(items=items)
