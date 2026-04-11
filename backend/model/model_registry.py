from sqlalchemy import Column, DateTime, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from backend.core.database import Base


class ModelRegistry(Base):
    """
    Model Registry：模型元数据 + 状态（active / canary / deprecated）。
    对象在 MinIO `models` bucket，路径存 object_path：{model_name}/{version}/model.pkl。
    同一 model_name 仅允许一条 active、一条 canary（由 service 层事务保证）。
    """

    __tablename__ = "model_registry"
    __table_args__ = (
        UniqueConstraint("model_name", "version", name="uq_model_registry_name_version"),
        Index("ix_model_registry_name_status", "model_name", "status"),
        Index("ix_model_registry_created", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(128), nullable=False)
    version = Column(String(32), nullable=False)
    feature_version = Column(String(32), nullable=False)
    object_path = Column(String(512), nullable=False)
    eval_accuracy = Column(Float, nullable=False)
    eval_precision = Column(Float, nullable=False)
    eval_recall = Column(Float, nullable=False)
    traffic_percent = Column(Integer, nullable=False, server_default="100")
    status = Column(String(32), nullable=False, server_default="deprecated")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
