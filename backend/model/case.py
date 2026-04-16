from sqlalchemy import Column, DateTime, Index, Integer, String, Text
from sqlalchemy.sql import func

from backend.core.database import Base


class Case(Base):
    """调查案件：前端案件管理的持久化存储。"""

    __tablename__ = "cases"
    __table_args__ = (
        Index("ix_cases_user_id", "user_id"),
        Index("ix_cases_user_status", "user_id", "status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    name = Column(String(256), nullable=False)
    case_number = Column(String(128), nullable=True)
    note = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, server_default="active")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
