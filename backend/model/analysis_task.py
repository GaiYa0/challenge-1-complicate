"""
分析任务（领域）：一次可追踪的异步分析作业，与 Celery 任务 ID 关联。

说明：与 celery_task_runs（运维监控）正交；本表为业务语义与幂等、结果引用。
"""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.sql import func

from backend.core.database import Base


class AnalysisTask(Base):
    __tablename__ = "analysis_tasks"
    __table_args__ = (
        Index("ix_analysis_tasks_case_id", "case_id"),
        Index("ix_analysis_tasks_case_status", "case_id", "status"),
        Index("ix_analysis_tasks_user_id", "user_id"),
        Index("ix_analysis_tasks_celery_id", "celery_task_id"),
        Index("ix_analysis_tasks_created_at", "created_at"),
        Index("ix_analysis_tasks_task_type", "task_type"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 对外 API 可用 UUID 字符串，避免暴露自增
    public_id = Column(String(36), nullable=False, unique=True)

    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # 任务类型：clean / feature_extract / graph_build / clue_generate / pipeline_composite
    task_type = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, server_default="queued")
    # queued / running / succeeded / failed / cancelled

    input_payload = Column(JSON, nullable=False)
    result_ref = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    celery_task_id = Column(String(64), nullable=True, index=True)

    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
