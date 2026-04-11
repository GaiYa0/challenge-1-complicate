"""最终失败后的补偿队列：审计、告警钩子占位。"""

from __future__ import annotations

import logging

from backend.tasks.celery_app import celery_app

_log = logging.getLogger("tasks.compensation")


@celery_app.task(name="tasks.compensation_record", ignore_result=True)
def compensation_record(payload: dict) -> dict:
    _log.error(
        "compensation_record task=%s celery_id=%s err=%s",
        payload.get("failed_task"),
        payload.get("task_id"),
        payload.get("error"),
    )
    return {"recorded": True, "failed_task": payload.get("failed_task")}
