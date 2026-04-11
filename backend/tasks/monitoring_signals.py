"""
任务监控：记录状态、耗时、重试次数到 celery_task_runs。
在 celery_app 加载任务模块之后 import 本模块即可注册信号。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from celery import signals
from sqlalchemy import select

from backend.model.celery_task_run import CeleryTaskRun
from backend.tasks import runtime
from backend.tasks.queue_config import CELERY_TASK_ROUTES
from backend.tasks.task_base import _extract_user_id

_log = logging.getLogger("celery.monitoring")


def _queue_for(name: str) -> str | None:
    r = CELERY_TASK_ROUTES.get(name)
    return r.get("queue") if r else None


def _get_by_task_id(db, task_id: str) -> CeleryTaskRun | None:
    return db.execute(
        select(CeleryTaskRun).where(CeleryTaskRun.celery_task_id == task_id).limit(1)
    ).scalar_one_or_none()


@signals.task_prerun.connect(weak=False)
def _task_prerun(sender=None, task_id=None, task=None, args=None, kwargs=None, **kw):
    if task is None or task_id is None:
        return
    tid = str(task_id)
    db = runtime.open_session()
    try:
        uid = _extract_user_id(task.name, tuple(args or ()), dict(kwargs or {}))
        now = datetime.now(timezone.utc)
        row = _get_by_task_id(db, tid)
        if row is None:
            row = CeleryTaskRun(
                celery_task_id=tid,
                task_name=task.name,
                queue=_queue_for(task.name),
                user_id=uid,
                state="RUNNING",
                retries=int(getattr(task.request, "retries", 0) or 0),
                started_at=now,
            )
            db.add(row)
        else:
            row.state = "RUNNING"
            row.retries = int(getattr(task.request, "retries", 0) or 0)
            row.started_at = now
            row.error_message = None
        db.commit()
    except Exception:
        db.rollback()
        _log.debug("task_prerun_monitor_skip", exc_info=True)
    finally:
        db.close()


@signals.task_postrun.connect(weak=False)
def _task_postrun(sender=None, task_id=None, task=None, state=None, retval=None, **kw):
    if task is None or task_id is None:
        return
    tid = str(task_id)
    db = runtime.open_session()
    try:
        row = _get_by_task_id(db, tid)
        if row is None:
            return
        now = datetime.now(timezone.utc)
        row.finished_at = now
        row.state = str(state or "SUCCESS")
        if row.started_at:
            row.duration_ms = (now - row.started_at).total_seconds() * 1000.0
        db.commit()
    except Exception:
        db.rollback()
        _log.debug("task_postrun_monitor_skip", exc_info=True)
    finally:
        db.close()


@signals.task_failure.connect(weak=False)
def _task_failure(sender=None, task_id=None, exception=None, args=None, kwargs=None, **kw):
    if sender is None or task_id is None:
        return
    task = sender
    try:
        max_r = int(getattr(task, "max_retries", 0) or 0)
        if int(getattr(task.request, "retries", 0) or 0) < max_r:
            return
    except Exception:
        pass
    tid = str(task_id)
    db = runtime.open_session()
    try:
        row = _get_by_task_id(db, tid)
        now = datetime.now(timezone.utc)
        if row is None:
            row = CeleryTaskRun(
                celery_task_id=tid,
                task_name=task.name,
                queue=_queue_for(task.name),
                user_id=_extract_user_id(task.name, tuple(args or ()), dict(kwargs or {})),
                state="FAILURE",
                retries=int(getattr(task.request, "retries", 0) or 0),
                started_at=now,
            )
            db.add(row)
        row.state = "FAILURE"
        row.finished_at = now
        row.error_message = str(exception)[:4000] if exception else None
        row.retries = int(getattr(task.request, "retries", 0) or 0)
        if row.started_at and row.finished_at:
            row.duration_ms = (row.finished_at - row.started_at).total_seconds() * 1000.0
        db.commit()
    except Exception:
        db.rollback()
        _log.debug("task_failure_monitor_skip", exc_info=True)
    finally:
        db.close()
