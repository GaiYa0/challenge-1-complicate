"""
超大计算预留：Spark 提交占位任务。

接入方式（示例）：
- 在 compute_router 返回 spark 时，由 API 投递本任务；
- Worker 内调用 spark-submit / K8s SparkApplication（此处仅占位日志）。
"""

from __future__ import annotations

import logging

from backend.tasks.celery_app import celery_app

_log = logging.getLogger("tasks.spark")


@celery_app.task(name="tasks.spark_placeholder_submit", bind=True)
def spark_placeholder_submit(self, job_name: str, payload: dict) -> dict:
    _log.info(
        "spark_placeholder_submit job=%s payload_keys=%s retry=%s",
        job_name,
        list(payload.keys()),
        getattr(self.request, "retries", 0),
    )
    return {"code": 0, "msg": "spark integration pending", "job": job_name}
