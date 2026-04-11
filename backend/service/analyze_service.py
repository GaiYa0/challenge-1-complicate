"""
Service 层 —— 分析任务投递（计算在 Celery Worker 执行）。
"""

from sqlalchemy.orm import Session

from backend.core.exceptions import ServiceError
from backend.model.models import User
from backend.schema.task import TaskEnqueueData
from backend.service.file_service import file_owner_user_id_if_accessible


def enqueue_analyze_job(db: Session, kind: str, filename: str, user: User) -> TaskEnqueueData:
    """投递 analyze_data_task；mock 不校验文件，其余 kind 需文件存在。"""
    from backend.tasks.analyze_task import analyze_data_task

    if kind != "mock":
        owner_id = file_owner_user_id_if_accessible(db, filename, user)
        if owner_id is None:
            raise ServiceError("file not found")
    else:
        owner_id = user.id

    result = analyze_data_task.delay(kind, filename, owner_id)
    return TaskEnqueueData(task_id=result.id)
