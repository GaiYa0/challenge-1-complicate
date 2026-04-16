"""导出审批：报告下载须先申请并由管理员审批。"""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.sql import func

from backend.core.database import Base


class ExportRequest(Base):
    __tablename__ = "export_requests"
    __table_args__ = (
        Index("ix_export_requests_applicant", "applicant_id"),
        Index("ix_export_requests_case", "case_id"),
        Index("ix_export_requests_status", "status"),
        Index("ix_export_requests_created", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    applicant_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    person_id = Column(String(256), nullable=False)
    file_format = Column(String(16), nullable=False)  # pdf | docx

    status = Column(String(32), nullable=False, server_default="pending")
    # pending | approved | rejected

    reviewer_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review_note = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
