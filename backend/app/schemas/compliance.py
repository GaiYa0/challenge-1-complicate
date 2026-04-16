"""合规：导出审批、审计日志 API 契约。"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class ExportRequestCreate(BaseModel):
    case_id: int = Field(ge=1)
    person_id: str = Field(min_length=1, max_length=256)
    file_format: Literal["pdf", "docx"] = "pdf"


class ExportRequestOut(BaseModel):
    id: int
    applicant_id: int
    case_id: int
    person_id: str
    file_format: str
    status: str
    reviewer_id: int | None = None
    review_note: str | None = None
    reviewed_at: str | None = None
    created_at: str


class ExportReviewBody(BaseModel):
    note: str | None = None


class AuditLogOut(BaseModel):
    id: int
    user_id: int | None
    case_id: int | None
    action: str
    resource_type: str
    resource_id: str | None
    ip_address: str | None
    detail: dict[str, Any] | None
    created_at: str
