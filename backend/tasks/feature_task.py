"""
特征提取任务：标准化流水线 → Feature Store（离线 DB + 在线 Redis），version 自动递增。
"""

from __future__ import annotations

import logging

from backend.repository import file_repo
from backend.service.feature_service import run_feature_generation
from backend.service import data_pipeline_service
from backend.tasks.celery_app import celery_app
from backend.tasks import runtime
from backend.tasks.task_base import QuotaTrackedTask

logger = logging.getLogger("tasks.feature_extract")


@celery_app.task(
    bind=True,
    base=QuotaTrackedTask,
    name="tasks.feature_extract_task",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 5, "countdown": 10},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def feature_extract_task(self, filename: str, user_id: int) -> dict:
    logger.info(
        "feature_extract_task start filename=%s user_id=%s retry=%s",
        filename,
        user_id,
        getattr(self.request, "retries", 0),
    )
    try:
        if not runtime.file_belongs_to_user(filename, user_id):
            return {"code": 1, "msg": "file not found", "data": None}

        mio = runtime.minio_client()
        rds = runtime.redis_client()
        db = runtime.open_session()
        try:
            row = file_repo.get_file_for_tenant(db, filename, user_id)
            if row is None:
                return {"code": 1, "msg": "file not found", "data": None}

            summary = data_pipeline_service.run_standard_pipeline(
                db, mio, filename=filename, user_id=user_id
            )
            meta = run_feature_generation(db, mio, rds, user_id=user_id, entity_id=int(row.id))
            return {
                "code": 0,
                "msg": "success",
                "data": {
                    "pipeline": summary,
                    "feature_store": meta,
                },
            }
        finally:
            db.close()
    except Exception:
        logger.exception(
            "feature_extract_task FAILED filename=%s user_id=%s retries=%s",
            filename,
            user_id,
            getattr(self.request, "retries", 0),
        )
        raise
