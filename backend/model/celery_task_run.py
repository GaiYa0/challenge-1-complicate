"""Celery 任务运行监控：状态、耗时、失败次数（由 worker 信号写入）。"""

from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.sql import func

from backend.core.database import Base


class CeleryTaskRun(Base):
    __tablename__ = "celery_task_runs"
    __table_args__ = (Index("ix_celery_task_runs_name_created", "task_name", "created_at"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    celery_task_id = Column(String(64), nullable=False, unique=True, index=True)
    task_name = Column(String(256), nullable=False)
    queue = Column(String(64), nullable=True)
    user_id = Column(Integer, nullable=True, index=True)
    state = Column(String(32), nullable=False, server_default="STARTED")
    retries = Column(Integer, nullable=False, server_default="0")
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    duration_ms = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
