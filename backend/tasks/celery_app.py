"""
Celery 应用：多队列（high_priority / default / low_priority / compensation）、路由与监控。

启动 Worker（项目根目录，已安装依赖），示例见 docs/CELERY_SCHEDULING.md：

    export PYTHONPATH=.
    celery -A backend.tasks.celery_app worker -Q high_priority -n worker_high@%h --concurrency=2 --loglevel=info
    celery -A backend.tasks.celery_app worker -Q default -n worker_default@%h --concurrency=4 --loglevel=info
    celery -A backend.tasks.celery_app worker -Q low_priority,compensation -n worker_low@%h --concurrency=2 --loglevel=info

Beat（周期任务）：

    celery -A backend.tasks.celery_app beat --loglevel=info

监控：`celery_task_runs` 表、或 Flower：

    celery -A backend.tasks.celery_app flower
"""

from celery import Celery
from celery.schedules import crontab

from backend.core.config import get_settings
from backend.tasks.queue_config import CELERY_TASK_QUEUES, CELERY_TASK_ROUTES

_settings = get_settings()

celery_app = Celery(
    "challenge_demo",
    broker=_settings.celery_broker,
    backend=_settings.celery_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    result_extended=True,
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_default_max_retries=int(_settings.CELERY_TASK_MAX_RETRIES),
    task_default_retry_delay=10,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_queues=CELERY_TASK_QUEUES,
    task_routes=CELERY_TASK_ROUTES,
    task_default_queue="default",
    task_create_missing_queues=True,
    beat_schedule={
        "mlops-nightly-retrain": {
            "task": "tasks.scheduled_retrain",
            "schedule": crontab(hour=2, minute=0),
            "kwargs": {"model_name": "default", "feature_version": "v1"},
        },
        "lifecycle-demote-hot-hourly": {
            "task": "tasks.lifecycle_demote_hot_to_warm",
            "schedule": crontab(minute=12),
        },
        "lifecycle-cold-archive-daily": {
            "task": "tasks.lifecycle_archive_warm_to_cold",
            "schedule": crontab(hour=4, minute=20),
        },
    },
)

# 注册任务模块（避免循环 import：在 app 实例化之后加载）
from backend.tasks import analyze_task  # noqa: E402, F401
from backend.tasks import clean_task  # noqa: E402, F401
from backend.tasks import compensation_tasks  # noqa: E402, F401
from backend.tasks import cost_tasks  # noqa: E402, F401
from backend.tasks import feature_task  # noqa: E402, F401
from backend.tasks import lifecycle_tasks  # noqa: E402, F401
from backend.tasks import model_tasks  # noqa: E402, F401
from backend.tasks import spark_placeholder  # noqa: E402, F401
import backend.tasks.monitoring_signals  # noqa: E402, F401  # 注册信号
