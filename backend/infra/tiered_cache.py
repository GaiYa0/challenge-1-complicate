"""
分级缓存示例：L1 进程内 TTL → L2 Redis → L3 数据库查询。

用于「文件元数据摘要」等读多写少场景；与 analyze 结果缓存（read_through_json）互补。
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any, Callable

from redis import Redis
from sqlalchemy.orm import Session

class _L1TTL:
    def __init__(self, *, max_items: int = 512, ttl_sec: float = 30.0):
        self._ttl = ttl_sec
        self._max = max_items
        self._data: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        now = time.monotonic()
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            exp, val = item
            if exp < now:
                del self._data[key]
                return None
            return val

    def set(self, key: str, value: Any) -> None:
        now = time.monotonic()
        with self._lock:
            if len(self._data) >= self._max:
                expired = [k for k, (exp, _) in self._data.items() if exp < now]
                for k in expired:
                    self._data.pop(k, None)
                if len(self._data) >= self._max:
                    oldest = sorted(self._data, key=lambda k: self._data[k][0])
                    for k in oldest[: self._max // 2]:
                        self._data.pop(k, None)
            self._data[key] = (now + self._ttl, value)


_l1 = _L1TTL()


def file_meta_cache_key(user_id: int, filename: str) -> str:
    return f"meta:file:{user_id}:{filename}"


def get_file_meta_tiered(
    *,
    redis: Redis,
    db: Session,
    user_id: int,
    filename: str,
    load_from_db: Callable[[], dict[str, Any]],
    l2_ttl_sec: int = 120,
) -> dict[str, Any]:
    k1 = f"l1:{user_id}:{filename}"
    hit = _l1.get(k1)
    if hit is not None:
        return dict(hit)

    k2 = file_meta_cache_key(user_id, filename)
    raw = redis.get(k2)
    if raw is not None:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            redis.delete(k2)
        else:
            _l1.set(k1, data)
            return data

    data = load_from_db()
    redis.setex(k2, l2_ttl_sec, json.dumps(data, default=str))
    _l1.set(k1, data)
    return data
