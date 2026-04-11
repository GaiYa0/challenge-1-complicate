"""
任务基类：单用户并发槽位（隔离 + 防滥用）与最终失败投递补偿队列。

并发槽位在 Task.__call__ 边界维护，避免仅排队不执行时误占槽位。
"""

from __future__ import annotations

import logging
from typing import Any

from celery import Task
from celery.exceptions import Reject

from backend.core.config import get_settings
from backend.tasks import runtime

_log = logging.getLogger("celery.task_base")


def _extract_user_id(task_name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> int | None:
    if task_name in ("tasks.analyze_data_task",):
        if len(args) >= 3:
            return int(args[2])
    if task_name in ("tasks.clean_data_task", "tasks.feature_extract_task"):
        if len(args) >= 2:
            return int(args[1])
    if task_name == "tasks.model_predict_task":
        if len(args) >= 1:
            return int(args[0])
    if task_name == "tasks.model_train_async_task":
        if len(args) >= 1:
            return int(args[0])
    if task_name == "tasks.retrain_on_feedback":
        uid = kwargs.get("tenant_user_id")
        return int(uid) if uid is not None else None
    return None


def _slot_key(user_id: int) -> str:
    return f"celery:user:active_slots:{user_id}"


def _try_acquire_slot(redis, user_id: int, limit: int) -> bool:
    k = _slot_key(user_id)
    n = int(redis.incr(k))
    redis.expire(k, 7200)
    if n > limit:
        redis.decr(k)
        return False
    return True


def _release_slot(redis, user_id: int) -> None:
    try:
        n = int(redis.decr(_slot_key(user_id)))
        if n < 0:
            redis.set(_slot_key(user_id), "0")
    except Exception:
        _log.warning("release_slot_failed user_id=%s", user_id, exc_info=True)


class QuotaTrackedTask(Task):
    """限制单用户同时执行的任务数；超限则 Reject(requeue=True) 回到队列（退避）。"""

    abstract = True

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        uid = _extract_user_id(self.name, args, kwargs)
        acquired = False
        redis = None
        if uid is not None:
            redis = runtime.redis_client()
            limit = int(get_settings().CELERY_MAX_CONCURRENT_PER_USER)
            if not _try_acquire_slot(redis, uid, limit):
                _log.warning("user_slot_rejected task=%s user_id=%s", self.name, uid)
                raise Reject("per-user concurrency limit", requeue=True)
            acquired = True
        try:
            return super().__call__(*args, **kwargs)
        finally:
            if acquired and redis is not None and uid is not None:
                _release_slot(redis, uid)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """仅在不再重试时投递补偿队列（request.retries >= max_retries 表示本次为终态失败）。"""
        try:
            max_r = int(getattr(self, "max_retries", 0) or 0)
            if self.request.retries < max_r:
                super().on_failure(exc, task_id, args, kwargs, einfo)
                return
            from backend.tasks.compensation_tasks import compensation_record

            compensation_record.delay(
                {
                    "failed_task": self.name,
                    "task_id": task_id,
                    "args": list(args) if args else [],
                    "kwargs": dict(kwargs) if kwargs else {},
                    "error": str(exc),
                }
            )
        except Exception:
            _log.exception("compensation_enqueue_failed task=%s", self.name)
        super().on_failure(exc, task_id, args, kwargs, einfo)
