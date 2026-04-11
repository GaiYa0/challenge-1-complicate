"""
生命周期定时任务：热→温、温→冷（MinIO gzip），配合 Beat 调度。
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from backend.core.config import get_settings
from backend.infra.redis_client import lifecycle_hot_meta_key
from backend.repository import file_repo
from backend.service import lifecycle_service
from backend.tasks import runtime
from backend.tasks.celery_app import celery_app

_log = logging.getLogger("tasks.lifecycle")


def _log_duration(name: str, t0: float, **extra):
    _log.info(
        "lifecycle_task_done name=%s duration_ms=%.1f extra=%s",
        name,
        (time.perf_counter() - t0) * 1000.0,
        extra,
    )


@celery_app.task(name="tasks.lifecycle_demote_hot_to_warm")
def lifecycle_demote_hot_to_warm() -> dict:
    """超过 7 天的 hot 标记为 warm，并清理 Redis 热元数据键。"""
    t0 = time.perf_counter()
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    db = runtime.open_session()
    r = runtime.redis_client()
    try:
        ids = file_repo.bulk_set_tier_warm_before(db, created_before=cutoff)
        for fid in ids:
            r.delete(lifecycle_hot_meta_key(fid))
        db.commit()
        out = {"demoted": len(ids)}
        dur_ms = (time.perf_counter() - t0) * 1000.0
        _log_duration("lifecycle_demote_hot_to_warm", t0, **out)
        try:
            from backend.tasks.cost_tasks import ingest_cost_metric_v1

            ingest_cost_metric_v1.delay(
                user_id=None,
                event_kind="task",
                name="lifecycle_demote_hot_to_warm",
                duration_ms=dur_ms,
                meta=out,
            )
        except Exception:
            pass
        return out
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="tasks.lifecycle_archive_warm_to_cold")
def lifecycle_archive_warm_to_cold() -> dict:
    """超过 30 天的 warm CSV 压缩写入 cold-data，并更新元数据。"""
    t0 = time.perf_counter()
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    db = runtime.open_session()
    client = runtime.minio_client()
    r = runtime.redis_client()
    archived = 0
    try:
        rows = file_repo.list_warm_files_older_than(
            db, created_before=cutoff, limit=settings.LIFECYCLE_COLD_ARCHIVE_BATCH
        )
        for row in rows:
            try:
                if lifecycle_service.archive_warm_row_to_cold(db, client, r, row):
                    archived += 1
                    db.commit()
            except Exception:
                db.rollback()
                _log.exception("cold_archive_failed file_id=%s", row.id)
        dur_ms = (time.perf_counter() - t0) * 1000.0
        _log_duration("lifecycle_archive_warm_to_cold", t0, archived=archived, scanned=len(rows))
        try:
            from backend.tasks.cost_tasks import ingest_cost_metric_v1

            ingest_cost_metric_v1.delay(
                user_id=None,
                event_kind="task",
                name="lifecycle_archive_warm_to_cold",
                duration_ms=dur_ms,
                meta={"archived": archived, "scanned": len(rows)},
            )
        except Exception:
            pass
        return {"archived": archived, "scanned": len(rows)}
    finally:
        db.close()
