"""
案件与文件关联：多对多，支撑「所有数据归属 case」。

说明：file_id 指向 files 表；业务上同一文件可被多个案件引用时需复制元数据或单独上传策略（由上层规则决定，本表仅约束绑定关系）。
"""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from backend.core.database import Base


class CaseFile(Base):
    __tablename__ = "case_files"
    __table_args__ = (
        UniqueConstraint("case_id", "file_id", name="uq_case_files_case_file"),
        Index("ix_case_files_case_id", "case_id"),
        Index("ix_case_files_file_id", "file_id"),
        Index("ix_case_files_case_created", "case_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    # 绑定角色：如 bank_statement / call_log / attachment，由上层枚举约束
    role = Column(String(64), nullable=True)
    sort_order = Column(Integer, nullable=False, server_default="0")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
