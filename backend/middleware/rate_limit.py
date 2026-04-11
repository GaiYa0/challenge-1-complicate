"""
基于 Redis 的按用户固定窗口限流：每分钟最多 N 次（与 core.config.RATE_LIMIT_REQUESTS_PER_MINUTE 一致）。
"""

from __future__ import annotations

import time

from redis import Redis

from backend.core.config import RATE_LIMIT_REQUESTS_PER_MINUTE
from backend.core.exceptions import RateLimitError


def _minute_bucket() -> int:
    return int(time.time()) // 60


def enforce_per_user_per_minute(redis: Redis, *, user_id: int) -> None:
    bucket = _minute_bucket()
    key = f"ratelimit:user:{user_id}:{bucket}"
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, 90)
    count, _ = pipe.execute()
    if int(count) > RATE_LIMIT_REQUESTS_PER_MINUTE:
        raise RateLimitError("rate limit exceeded", code=42901)
