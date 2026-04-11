from sqlalchemy import Column, DateTime, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.sql import func

from backend.core.database import Base


class Feature(Base):
    """
    Feature Store：一行一个特征（宽表拆行），便于按 entity + version 查询与训练对齐。
    entity_id 通常为 files.id（数据对象主键）。
    """

    __tablename__ = "features"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "entity_id", "feature_name", "version",
            name="uq_features_user_entity_name_version",
        ),
        Index("ix_features_user_entity_version", "user_id", "entity_id", "version"),
        Index("ix_features_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    entity_id = Column(Integer, nullable=False)
    feature_name = Column(String(256), nullable=False)
    feature_value = Column(JSON, nullable=True)
    version = Column(String(32), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
