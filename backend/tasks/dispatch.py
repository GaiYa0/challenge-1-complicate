"""
任务分发入口：显式 apply_async（队列由 task_routes 绑定，此处便于单测与文档引用）。

业务代码可继续直接使用 `*.delay()`；路由在 `queue_config.CELERY_TASK_ROUTES` 中统一维护。
"""

from __future__ import annotations

from typing import Any

from celery.result import AsyncResult

from backend.tasks.analyze_task import analyze_data_task
from backend.tasks.clean_task import clean_data_task
from backend.tasks.feature_task import feature_extract_task
from backend.tasks.model_tasks import model_predict_task, model_train_async_task
from backend.tasks.queue_config import QUEUE_DEFAULT, QUEUE_HIGH, QUEUE_LOW


def submit_predict(user_id: int, filename: str, model_name: str = "default") -> AsyncResult[Any]:
    return model_predict_task.apply_async(
        args=(user_id, filename, model_name),
        queue=QUEUE_HIGH,
    )


def submit_analyze(kind: str, filename: str, user_id: int) -> AsyncResult[Any]:
    return analyze_data_task.apply_async(args=(kind, filename, user_id), queue=QUEUE_DEFAULT)


def submit_clean(filename: str, user_id: int) -> AsyncResult[Any]:
    return clean_data_task.apply_async(args=(filename, user_id), queue=QUEUE_DEFAULT)


def submit_feature_extract(filename: str, user_id: int) -> AsyncResult[Any]:
    return feature_extract_task.apply_async(args=(filename, user_id), queue=QUEUE_DEFAULT)


def submit_train_async(
    user_id: int,
    model_name: str = "default",
    feature_version: str = "v1",
    use_all_features: bool = False,
) -> AsyncResult[Any]:
    return model_train_async_task.apply_async(
        args=(user_id, model_name, feature_version, use_all_features),
        queue=QUEUE_LOW,
    )
