"""报告导出 API 契约。"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class ReportGenerateIn(BaseModel):
    case_id: int = Field(ge=1)
    person_id: str = Field(min_length=1, max_length=256)
    format: Literal["pdf", "docx"] = "pdf"
    """非 admin 且开启合规开关时，必须填写已审批的导出申请 ID。"""
    export_request_id: int | None = None


class ReportTaskQueued(BaseModel):
    task_id: str
    status: str = "PENDING"
    poll_url: str = Field(description="轮询任务状态与下载链接")


class ReportTaskResultOut(BaseModel):
    task_id: str
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None
