"""成本与 SLA 观测：HTTP 与异步任务写入（异步 Celery 落库）。"""

from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.sql import func

from backend.core.database import Base


class CostMetric(Base):
    __tablename__ = "cost_metrics"
    __table_args__ = (
        Index("ix_cost_metrics_user_created", "user_id", "created_at"),
        Index("ix_cost_metrics_kind_created", "event_kind", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True, index=True)
    event_kind = Column(String(32), nullable=False)
    name = Column(String(512), nullable=False)
    duration_ms = Column(Float, nullable=False)
    bytes_in = Column(Integer, nullable=True)
    bytes_out = Column(Integer, nullable=True)
    meta_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
