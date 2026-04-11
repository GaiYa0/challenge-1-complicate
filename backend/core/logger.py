"""
JSON 行日志：timestamp / level / message + request_id / user_id / path / latency_ms（由 extra 注入）。
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    """将 LogRecord 格式化为单行 JSON。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        for key in (
            "request_id",
            "user_id",
            "path",
            "latency_ms",
            "cache_hits",
            "cache_misses",
            "cache_hit_ratio",
            "db_query_ms",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    root.addHandler(h)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


ACCESS_LOGGER_NAME = "app.access"


def log_http_access(
    *,
    request_id: str,
    path: str,
    latency_ms: float,
    user_id: int | None,
    cache_hits: int | None = None,
    cache_misses: int | None = None,
    cache_hit_ratio: float | None = None,
    db_query_ms: float | None = None,
    level: int = logging.INFO,
) -> None:
    extra: dict[str, Any] = {
        "request_id": request_id,
        "user_id": user_id,
        "path": path,
        "latency_ms": round(latency_ms, 3),
    }
    if cache_hits is not None:
        extra["cache_hits"] = cache_hits
    if cache_misses is not None:
        extra["cache_misses"] = cache_misses
    if cache_hit_ratio is not None:
        extra["cache_hit_ratio"] = cache_hit_ratio
    if db_query_ms is not None:
        extra["db_query_ms"] = round(db_query_ms, 3)
    logging.getLogger(ACCESS_LOGGER_NAME).log(level, "http_request", extra=extra)
