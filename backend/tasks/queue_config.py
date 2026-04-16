"""
Celery 多队列：高 / 默认 / 低 / 补偿。
与 worker 启动参数 `-Q` 组合，实现资源隔离与近似优先级抢占。
"""

from __future__ import annotations

from kombu import Exchange, Queue

# 与文档、worker 启动命令保持一致
QUEUE_HIGH = "high_priority"
QUEUE_DEFAULT = "default"
QUEUE_LOW = "low_priority"
QUEUE_COMPENSATION = "compensation"

_default_exchange = Exchange("celery", type="direct")

CELERY_TASK_QUEUES = (
    Queue(QUEUE_HIGH, exchange=_default_exchange, routing_key=QUEUE_HIGH),
    Queue(QUEUE_DEFAULT, exchange=_default_exchange, routing_key=QUEUE_DEFAULT),
    Queue(QUEUE_LOW, exchange=_default_exchange, routing_key=QUEUE_LOW),
    Queue(QUEUE_COMPENSATION, exchange=_default_exchange, routing_key=QUEUE_COMPENSATION),
)

# 任务名 → 队列（predict=high, analyze=clean/feature=default, train=low）
CELERY_TASK_ROUTES: dict[str, dict[str, str]] = {
    "tasks.model_predict_task": {"queue": QUEUE_HIGH},
    "tasks.analyze_data_task": {"queue": QUEUE_DEFAULT},
    "tasks.clean_data_task": {"queue": QUEUE_DEFAULT},
    "tasks.feature_extract_task": {"queue": QUEUE_DEFAULT},
    "tasks.ingest_cost_metric_v1": {"queue": QUEUE_DEFAULT},
    "tasks.scheduled_retrain": {"queue": QUEUE_LOW},
    "tasks.retrain_on_feedback": {"queue": QUEUE_LOW},
    "tasks.check_feedback_retrain": {"queue": QUEUE_LOW},
    "tasks.model_train_async_task": {"queue": QUEUE_LOW},
    "tasks.lifecycle_demote_hot_to_warm": {"queue": QUEUE_LOW},
    "tasks.lifecycle_archive_warm_to_cold": {"queue": QUEUE_LOW},
    "tasks.spark_placeholder_submit": {"queue": QUEUE_LOW},
    "tasks.report_generate_task": {"queue": QUEUE_LOW},
    "tasks.compensation_record": {"queue": QUEUE_COMPENSATION},
}
