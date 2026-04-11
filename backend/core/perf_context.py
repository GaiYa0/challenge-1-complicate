"""
请求级性能指标（ContextVar）：缓存命中/未命中、DB 累计耗时。
由中间件 reset，Service / Redis 封装在同步路径中累加。
"""

from __future__ import annotations

import time
from contextvars import ContextVar
from typing import Any

_perf: ContextVar[dict[str, Any] | None] = ContextVar("perf_metrics", default=None)


def reset_perf_metrics() -> None:
    _perf.set({"cache_hits": 0, "cache_misses": 0, "db_ms": 0.0})


def get_perf_metrics() -> dict[str, Any] | None:
    return _perf.get()


def record_cache_hit() -> None:
    m = _perf.get()
    if m is not None:
        m["cache_hits"] = int(m.get("cache_hits", 0)) + 1


def record_cache_miss() -> None:
    m = _perf.get()
    if m is not None:
        m["cache_misses"] = int(m.get("cache_misses", 0)) + 1


def add_db_time_ms(delta_ms: float) -> None:
    m = _perf.get()
    if m is not None:
        m["db_ms"] = float(m.get("db_ms", 0.0)) + float(delta_ms)
