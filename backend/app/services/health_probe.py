"""
健康探针：/live 只看进程存活；/ready 探测关键依赖（DB/Redis/MinIO/Neo4j）。

为防探活雪崩：
- 每个依赖带 timeout；
- 结果在 Redis 里缓存 `HEALTH_READY_TTL_SEC` 秒（默认 5s）；
- Redis 不可用时退化为进程内 TTLCache。
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FutTimeout
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import FastAPI
from minio import Minio
from neo4j import Driver
from redis import Redis
from sqlalchemy import text
from sqlalchemy.engine import Engine

_log = logging.getLogger("health")

READY_CACHE_KEY = "health:ready:v1"
READY_CACHE_TTL_SEC = 5
PROBE_TIMEOUT_SEC = 1.5

_EXECUTOR = ThreadPoolExecutor(max_workers=6, thread_name_prefix="healthprobe")
_LOCAL_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


@dataclass
class ProbeResult:
    name: str
    ok: bool
    latency_ms: float
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"ok": self.ok, "latency_ms": round(self.latency_ms, 2)}
        if self.detail:
            out["detail"] = self.detail
        return out


def _timed(fn: Callable[[], Any]) -> ProbeResult:
    t0 = time.perf_counter()
    name = getattr(fn, "__name__", "probe").replace("_probe_", "")
    try:
        fut = _EXECUTOR.submit(fn)
        fut.result(timeout=PROBE_TIMEOUT_SEC)
        return ProbeResult(name=name, ok=True, latency_ms=(time.perf_counter() - t0) * 1000)
    except _FutTimeout:
        return ProbeResult(
            name=name,
            ok=False,
            latency_ms=PROBE_TIMEOUT_SEC * 1000,
            detail="timeout",
        )
    except Exception as exc:
        return ProbeResult(
            name=name,
            ok=False,
            latency_ms=(time.perf_counter() - t0) * 1000,
            detail=str(exc)[:200],
        )


def _probe_db(engine: Engine) -> ProbeResult:
    def _fn() -> None:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    _fn.__name__ = "_probe_db"
    return _timed(_fn)


def _probe_redis(redis: Redis | None) -> ProbeResult:
    def _fn() -> None:
        if redis is None:
            raise RuntimeError("redis not configured")
        if not redis.ping():
            raise RuntimeError("ping returned false")

    _fn.__name__ = "_probe_redis"
    return _timed(_fn)


def _probe_minio(minio: Minio | None) -> ProbeResult:
    def _fn() -> None:
        if minio is None:
            raise RuntimeError("minio not configured")
        # list_buckets 是最轻的权限探测
        list(minio.list_buckets())

    _fn.__name__ = "_probe_minio"
    return _timed(_fn)


def _probe_neo4j(driver: Driver | None) -> ProbeResult:
    def _fn() -> None:
        if driver is None:
            raise RuntimeError("neo4j not configured")
        driver.verify_connectivity()

    _fn.__name__ = "_probe_neo4j"
    return _timed(_fn)


def _cache_get(redis: Redis | None) -> dict[str, Any] | None:
    now = time.time()
    try:
        if redis is not None:
            raw = redis.get(READY_CACHE_KEY)
            if raw:
                import json

                data = json.loads(raw)
                if isinstance(data, dict):
                    return data
    except Exception:
        _log.debug("health_cache_redis_get_failed", exc_info=True)

    entry = _LOCAL_CACHE.get(READY_CACHE_KEY)
    if entry:
        ts, data = entry
        if now - ts <= READY_CACHE_TTL_SEC:
            return data
    return None


def _cache_set(redis: Redis | None, data: dict[str, Any]) -> None:
    try:
        if redis is not None:
            import json

            redis.setex(READY_CACHE_KEY, READY_CACHE_TTL_SEC, json.dumps(data))
    except Exception:
        _log.debug("health_cache_redis_set_failed", exc_info=True)
    _LOCAL_CACHE[READY_CACHE_KEY] = (time.time(), data)


def _collect_readiness(app: FastAPI) -> dict[str, Any]:
    state = app.state
    engine: Engine | None = getattr(state, "engine", None)
    redis: Redis | None = getattr(state, "redis", None)
    minio: Minio | None = getattr(state, "minio", None)
    driver: Driver | None = getattr(state, "neo4j_driver", None)

    probes: dict[str, ProbeResult] = {}
    probes["db"] = _probe_db(engine) if engine is not None else ProbeResult(
        "db", False, 0.0, "engine not ready"
    )
    probes["redis"] = _probe_redis(redis)
    probes["minio"] = _probe_minio(minio)
    probes["neo4j"] = _probe_neo4j(driver)

    critical_ok = probes["db"].ok  # DB 是唯一硬依赖
    all_ok = all(p.ok for p in probes.values())
    return {
        "status": "ready" if critical_ok else "unready",
        "all_ok": all_ok,
        "checks": {k: v.to_dict() for k, v in probes.items()},
    }


def check_liveness() -> dict[str, Any]:
    return {"status": "live"}


def check_readiness(app: FastAPI, *, force: bool = False) -> tuple[dict[str, Any], bool]:
    """
    返回 (payload, is_ready)。
    - `is_ready=False` 时 FastAPI 返回 503，让 k8s / LB 把该实例摘除。
    - DB 不可达即 503；其余探活失败只在 payload 中呈现，不影响 ready 判定。
    """
    redis: Redis | None = getattr(app.state, "redis", None)
    if not force:
        cached = _cache_get(redis)
        if cached is not None:
            return cached, bool(cached.get("status") == "ready")

    data = _collect_readiness(app)
    _cache_set(redis, data)
    return data, bool(data.get("status") == "ready")
