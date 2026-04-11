from sqlalchemy import Column, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from backend.core.database import Base


class File(Base):
    """
    文件元数据：对象在 MinIO，库中仅存 bucket / object / version 与逻辑文件名。
    """

    __tablename__ = "files"
    __table_args__ = (
        UniqueConstraint("user_id", "object_name", name="uq_files_user_object"),
        Index("ix_files_user_id_filename", "user_id", "filename"),
        Index("ix_files_user_created", "user_id", "created_at"),
        Index("ix_files_created_at", "created_at"),
        Index("ix_files_lifecycle_created", "lifecycle_tier", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    filename = Column(String(512), nullable=False)
    bucket_name = Column(String(128), nullable=False)
    object_name = Column(String(1024), nullable=False)
    version = Column(String(64), nullable=False)
    dataset = Column(String(256), nullable=False, server_default="default")
    data_layer = Column(String(32), nullable=False, server_default="raw")
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # --- 生命周期 / 成本优化（冷热分层 + 分月路由键）---
    lifecycle_tier = Column(String(16), nullable=False, server_default="hot")
    last_accessed_at = Column(DateTime, nullable=True)
    access_count = Column(Integer, nullable=False, server_default="0")
    warm_month_key = Column(String(7), nullable=True, index=True)
    cold_bucket_name = Column(String(128), nullable=True)
    cold_object_name = Column(String(1024), nullable=True)
    archive_format = Column(String(32), nullable=False, server_default="none")
