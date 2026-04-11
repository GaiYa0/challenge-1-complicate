"""
清洗任务：标准化流水线后写入 processed-data + 元数据入库。
"""

from __future__ import annotations

import logging
import uuid
from io import BytesIO

from backend.core.config import get_settings
from backend.core.transaction import transaction
from backend.infra import minio_client as minio_ops
from backend.model.enums import DataLayer
from backend.repository import file_repo
from backend.service import data_pipeline_service
from backend.tasks.celery_app import celery_app
from backend.tasks import runtime
from backend.tasks.feature_task import feature_extract_task
from backend.tasks.task_base import QuotaTrackedTask

logger = logging.getLogger("tasks.clean_data")


@celery_app.task(
    bind=True,
    base=QuotaTrackedTask,
    name="tasks.clean_data_task",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 5, "countdown": 10},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def clean_data_task(self, filename: str, user_id: int) -> dict:
    logger.info(
        "clean_data_task start filename=%s user_id=%s retry=%s",
        filename,
        user_id,
        getattr(self.request, "retries", 0),
    )
    try:
        if not runtime.file_belongs_to_user(filename, user_id):
            return {"code": 1, "msg": "file not found", "data": None}

        mio = runtime.minio_client()
        db = runtime.open_session()
        try:
            df_clean, pipeline_summary = data_pipeline_service.run_pipeline_dataframe(
                db, mio, filename=filename, user_id=user_id
            )
            src = file_repo.get_file_for_tenant(db, filename, user_id)
            dataset_src = src.dataset if src else "default"
            logical_out = f"clean_{uuid.uuid4().hex[:8]}_{filename}"
            bucket = minio_ops.bucket_for_layer(DataLayer.CLEAN.value)
            object_name = minio_ops.build_object_name(
                user_id, f"{dataset_src}_clean", "v1", logical_out, layer="clean"
            )
            buf = BytesIO()
            df_clean.to_csv(buf, index=False)
            raw_out = buf.getvalue()
            minio_ops.put_bytes(mio, bucket, object_name, raw_out)
            try:
                with transaction(db):
                    file_repo.insert_file(
                        db,
                        user_id=user_id,
                        filename=logical_out,
                        bucket_name=bucket,
                        object_name=object_name,
                        version="v1",
                        dataset=f"{dataset_src}_clean",
                        data_layer=DataLayer.CLEAN.value,
                    )
            except Exception:
                minio_ops.remove_object(mio, bucket, object_name)
                raise
            settings = get_settings()
            if settings.KAFKA_ENABLED:
                from backend.events.producer import publish_data_processed

                publish_data_processed(user_id, logical_out)
            elif settings.KAFKA_UPLOAD_FALLBACK_CELERY:
                feature_extract_task.delay(logical_out, user_id)
            return {
                "code": 0,
                "msg": "success",
                "data": {
                    "output_filename": logical_out,
                    "bucket": bucket,
                    "object_name": object_name,
                    "pipeline": pipeline_summary,
                },
            }
        finally:
            db.close()
    except Exception:
        logger.exception(
            "clean_data_task FAILED filename=%s user_id=%s retries=%s",
            filename,
            user_id,
            getattr(self.request, "retries", 0),
        )
        raise
