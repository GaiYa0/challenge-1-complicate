"""
异步生成正式报告（PDF/Word），上传 MinIO，返回预签名下载 URL。
"""

from __future__ import annotations

import logging
import re
import threading
import unicodedata
import uuid
from typing import Any

from neo4j import Driver, GraphDatabase

from backend.core.config import get_settings
from backend.infra import minio_client as minio_ops
from backend.app.repositories import user_repo
from backend.app.services import portrait_service, report_export_service
from backend.tasks.celery_app import celery_app
from backend.tasks import runtime

logger = logging.getLogger("tasks.report_export")

_driver_lock = threading.Lock()
_driver_cached: Driver | None = None


def _get_driver() -> Driver:
    global _driver_cached
    if _driver_cached is not None:
        return _driver_cached
    with _driver_lock:
        if _driver_cached is None:
            s = get_settings()
            _driver_cached = GraphDatabase.driver(
                s.NEO4J_URI,
                auth=(s.NEO4J_USER, s.NEO4J_PASSWORD),
            )
        return _driver_cached


def _safe_segment(s: str, max_len: int = 64) -> str:
    try:
        norm = unicodedata.normalize("NFKC", str(s or ""))
    except Exception:
        norm = str(s or "")
    t = re.sub(r"[^\w\u4e00-\u9fff\-_.]", "_", norm.strip())[:max_len]
    return t or "person"


_RETRYABLE_EXC = (ConnectionError, TimeoutError, OSError)


@celery_app.task(
    bind=True,
    name="tasks.report_generate_task",
    autoretry_for=_RETRYABLE_EXC,
    retry_kwargs={"max_retries": 3, "countdown": 15},
    retry_backoff=True,
    acks_late=True,
)
def report_generate_task(
    self,
    user_id: int,
    case_id: int,
    person_id: str,
    fmt: str,
) -> dict[str, Any]:
    """
    fmt: pdf | docx
    返回：download_url、bucket、object_name、expires_in_seconds
    """
    driver = _get_driver()
    db = runtime.open_session()
    try:
        user = user_repo.get_user_by_id(db, user_id)
        if user is None:
            return {"code": 1, "msg": "user not found", "data": None}

        portrait = portrait_service.get_person_portrait(
            db,
            driver,
            user=user,
            case_id=case_id,
            person_id=person_id,
        )
        payload = portrait.model_dump(mode="json")

        if fmt == "pdf":
            raw = report_export_service.render_pdf_bytes(payload)
            content_type = "application/pdf"
            ext = "pdf"
        elif fmt == "docx":
            raw = report_export_service.render_docx_bytes(payload)
            content_type = (
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            )
            ext = "docx"
        else:
            return {"code": 2, "msg": "invalid format", "data": None}

        mio = runtime.minio_client()
        uid = uuid.uuid4().hex[:12]
        safe_p = _safe_segment(person_id)
        object_name = f"reports/{user_id}/{case_id}/{safe_p}_{uid}.{ext}"
        minio_ops.put_bytes(
            mio,
            minio_ops.BUCKET_REPORTS,
            object_name,
            raw,
            content_type=content_type,
        )
        expires = 86_400
        url = minio_ops.presigned_get_url(
            mio,
            minio_ops.BUCKET_REPORTS,
            object_name,
            expires_seconds=expires,
        )
        return {
            "code": 0,
            "msg": "ok",
            "data": {
                "download_url": url,
                "bucket": minio_ops.BUCKET_REPORTS,
                "object_name": object_name,
                "expires_in_seconds": expires,
                "format": fmt,
            },
        }
    except _RETRYABLE_EXC:
        logger.warning(
            "report_generate_task transient failure user=%s case=%s person=%s fmt=%s",
            user_id,
            case_id,
            person_id,
            fmt,
            exc_info=True,
        )
        raise
    except Exception:
        logger.exception(
            "report_generate_task permanent failure user=%s case=%s person=%s fmt=%s",
            user_id,
            case_id,
            person_id,
            fmt,
        )
        return {"code": 3, "msg": "report generation failed", "data": None}
    finally:
        try:
            db.close()
        except Exception:
            pass
