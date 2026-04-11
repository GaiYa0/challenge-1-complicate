"""成本指标异步落库，避免阻塞 API 线程。"""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from backend.model.cost_metric import CostMetric
from backend.tasks import runtime
from backend.tasks.celery_app import celery_app

_log = logging.getLogger("tasks.cost")

_MAX_META_JSON_LEN = 8000


def _safe_truncate_json(meta: dict, max_len: int = _MAX_META_JSON_LEN) -> str:
    """序列化 meta dict；若超长则逐步裁剪键直到合法 JSON 不超限。"""
    full = json.dumps(meta, ensure_ascii=False, default=str)
    if len(full) <= max_len:
        return full
    trimmed = dict(meta)
    trimmed["_truncated"] = True
    for key in list(trimmed.keys()):
        if key == "_truncated":
            continue
        trimmed.pop(key)
        candidate = json.dumps(trimmed, ensure_ascii=False, default=str)
        if len(candidate) <= max_len:
            return candidate
    return json.dumps({"_truncated": True})


@celery_app.task(name="tasks.ingest_cost_metric_v1", ignore_result=True)
def ingest_cost_metric_v1(
    *,
    user_id: int | None,
    event_kind: str,
    name: str,
    duration_ms: float,
    bytes_in: int | None = None,
    bytes_out: int | None = None,
    meta: dict | None = None,
) -> None:
    db: Session = runtime.open_session()
    try:
        row = CostMetric(
            user_id=user_id,
            event_kind=event_kind,
            name=name[:512],
            duration_ms=float(duration_ms),
            bytes_in=bytes_in,
            bytes_out=bytes_out,
            meta_json=_safe_truncate_json(meta) if meta else None,
        )
        db.add(row)
        db.commit()
    except Exception:
        db.rollback()
        _log.warning("cost_metric_write_failed", exc_info=True)
    finally:
        db.close()
