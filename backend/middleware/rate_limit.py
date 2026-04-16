"""
基于 Redis 的按用户固定窗口 + 短时突发双层限流。

- 分钟级：防止长期滥用（默认 600 次 / 分钟，可 env 调整）。
- 秒级突发：防止轮询风暴（默认 10 秒窗口内最多 120 次）。

豁免路径：`Settings.RATE_LIMIT_EXEMPT_PREFIXES`（默认覆盖 /task/、/auth/me、健康/指标）。
"""

from __future__ import annotations

import time
from typing import NamedTuple

from redis import Redis

from backend.core.config import RATE_LIMIT_REQUESTS_PER_MINUTE, get_settings
from backend.core.exceptions import RateLimitError


class RateLimitDecision(NamedTuple):
    blocked: bool
    retry_after: int  # 秒
    bucket_kind: str


def _current_minute_key(user_id: int) -> str:
    return f"ratelimit:user:{user_id}:min:{int(time.time()) // 60}"


def _current_burst_key(user_id: int, window_sec: int) -> str:
    win = max(2, int(window_sec))
    return f"ratelimit:user:{user_id}:burst{win}:{int(time.time()) // win}"


def is_exempt(path: str) -> bool:
    """根据配置前缀判断是否豁免限流。"""
    if not path:
        return False
    try:
        prefixes = get_settings().rate_limit_exempt_prefixes
    except Exception:
        prefixes = tuple()
    for pref in prefixes:
        if not pref:
            continue
        if pref.endswith("/"):
            if path.startswith(pref):
                return True
        elif path == pref or path.startswith(pref + "/"):
            return True
    return False


def _limit_minute(redis: Redis, *, user_id: int, ceiling: int) -> RateLimitDecision:
    key = _current_minute_key(user_id)
    try:
        pipe = redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, 90)
        count, _ = pipe.execute()
    except Exception:
        # Redis 故障时放行，避免整站瘫痪（由网关/上游兜底）
        return RateLimitDecision(blocked=False, retry_after=0, bucket_kind="minute")
    if int(count) > int(ceiling):
        retry = max(1, 60 - int(time.time()) % 60)
        return RateLimitDecision(blocked=True, retry_after=retry, bucket_kind="minute")
    return RateLimitDecision(blocked=False, retry_after=0, bucket_kind="minute")


def _limit_burst(
    redis: Redis, *, user_id: int, window_sec: int, ceiling: int
) -> RateLimitDecision:
    if int(ceiling) <= 0:
        return RateLimitDecision(blocked=False, retry_after=0, bucket_kind="burst")
    key = _current_burst_key(user_id, window_sec)
    try:
        pipe = redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, max(4, int(window_sec) * 2))
        count, _ = pipe.execute()
    except Exception:
        return RateLimitDecision(blocked=False, retry_after=0, bucket_kind="burst")
    if int(count) > int(ceiling):
        win = max(2, int(window_sec))
        retry = max(1, win - int(time.time()) % win)
        return RateLimitDecision(blocked=True, retry_after=retry, bucket_kind="burst")
    return RateLimitDecision(blocked=False, retry_after=0, bucket_kind="burst")


def check_rate_limit(redis: Redis, *, user_id: int, path: str) -> RateLimitDecision:
    """返回限流决策；调用方按 decision.blocked 决定是否抛出 RateLimitError。"""
    if is_exempt(path):
        return RateLimitDecision(blocked=False, retry_after=0, bucket_kind="exempt")

    settings = get_settings()
    minute_ceiling = int(
        getattr(settings, "RATE_LIMIT_REQUESTS_PER_MINUTE", RATE_LIMIT_REQUESTS_PER_MINUTE)
    )
    burst_window = int(getattr(settings, "RATE_LIMIT_BURST_BUCKET_SEC", 10))
    burst_ceiling = int(getattr(settings, "RATE_LIMIT_BURST_PER_BUCKET", 120))

    burst = _limit_burst(
        redis, user_id=user_id, window_sec=burst_window, ceiling=burst_ceiling
    )
    if burst.blocked:
        return burst
    return _limit_minute(redis, user_id=user_id, ceiling=minute_ceiling)


def enforce_per_user_per_minute(redis: Redis, *, user_id: int, path: str = "") -> None:
    """兼容旧入口：内部走双层限流。"""
    decision = check_rate_limit(redis, user_id=user_id, path=path)
    if decision.blocked:
        err = RateLimitError("rate limit exceeded", code=42901)
        setattr(err, "retry_after", int(decision.retry_after))
        raise err
