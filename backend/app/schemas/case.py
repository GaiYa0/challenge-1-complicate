from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    case_number: str | None = Field(default=None, max_length=128)
    note: str | None = None


class CaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    case_number: str | None = Field(default=None, max_length=128)
    note: str | None = None
    status: str | None = Field(default=None, pattern=r"^(active|completed)$")


class CaseOut(BaseModel):
    id: int
    name: str
    case_number: str | None = None
    note: str | None = None
    status: str
    extra_metadata: dict[str, Any] | None = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}
