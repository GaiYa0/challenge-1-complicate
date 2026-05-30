from sqlalchemy import Column, DateTime, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from backend.core.database import Base


class FieldMappingMemory(Base):
    __tablename__ = "field_mapping_memory"
    __table_args__ = (
        Index("ix_fmm_user_signature", "user_id", "header_signature"),
        Index("ix_fmm_last_used", "last_used_at"),
        UniqueConstraint(
            "user_id",
            "header_signature",
            "source_field",
            name="uq_fmm_user_header_source",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    header_signature = Column(String(512), nullable=False)
    source_field = Column(String(256), nullable=False)
    target_field = Column(String(128), nullable=False)
    confidence = Column(Float, nullable=False, server_default="0")
    hit_count = Column(Integer, nullable=False, server_default="0")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    last_used_at = Column(DateTime, nullable=False, server_default=func.now())
