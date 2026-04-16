"""线索 API 响应模型（与路由 response_model 配合，亦可直接返回 dict）。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ClueListItem(BaseModel):
    id: int
    title: str
    risk_level: str
    risk_score: float = Field(..., ge=0, le=100)


class ClueDetailOut(BaseModel):
    id: int
    case_id: int
    person_id: str
    title: str
    summary: str | None = None
    category: str
    risk_level: str
    risk_score: float
    rule_hits: list[Any]
    feature_snapshot: dict[str, Any]
    risk_prompts: list[Any]
    created_at: str
    updated_at: str
