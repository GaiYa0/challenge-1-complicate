"""
统一事件信封（Kafka value JSON）：仅允许四字段，便于跨服务契约校验。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: str = Field(..., min_length=1, max_length=64)
    user_id: int = Field(..., ge=0)
    resource_id: str = Field(..., min_length=1, max_length=1024)
    timestamp: str = Field(..., min_length=10, max_length=64)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_envelope(*, event_type: str, user_id: int, resource_id: str) -> dict[str, Any]:
    ev = EventEnvelope(
        event_type=event_type,
        user_id=int(user_id),
        resource_id=str(resource_id),
        timestamp=utc_now_iso(),
    )
    return ev.model_dump()


def parse_envelope(data: dict[str, Any]) -> EventEnvelope:
    return EventEnvelope.model_validate(data)
