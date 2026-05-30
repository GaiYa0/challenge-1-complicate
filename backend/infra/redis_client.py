"""
Redis 缓存封装：统一 key、TTL 抖动、JSON 读写、SETNX 防击穿、失效。

Key 规范（必须）：
  analyze:{type}:{user_id}:{resource_id}
  例：analyze:stats:1:file123.csv
  resource_id 一般为业务侧文件名/数据集 ID，禁止包含未转义的分段符。
"""

from __future__ import annotations

import json
import logging
import random
import time
import uuid
from collections.abc import Callable
from typing import Any

from redis import Redis

_log = logging.getLogger("redis.cache")

# --- TTL：基础 300s + 随机 0..100 防雪崩 ---
DEFAULT_CACHE_BASE_TTL = 300
DEFAULT_CACHE_JITTER_MAX = 100

# --- 分布式锁（防击穿）---
DEFAULT_LOCK_TTL_SEC = 30
DEFAULT_LOCK_WAIT_SEC = 3.0
DEFAULT_LOCK_POLL_SEC = 0.05


def analyze_cache_key(type_: str, user_id: int, resource_id: str) -> str:
    """统一 analyze 域缓存键。"""
    rid = str(resource_id).strip()
    return f"analyze:{type_}:{user_id}:{rid}"


def lock_key_for(cache_key: str) -> str:
    """与业务键一一对应的互斥锁键。"""
    return f"lock:{cache_key}"


def files_list_cache_key(user_id: int) -> str:
    """高频列表缓存（非 analyze 域，仍走同一 Redis 客户端）。"""
    return f"files:list:{user_id}"


def lifecycle_hot_meta_key(file_id: int) -> str:
    """热层：文件元数据摘要缓存（约 7 天 TTL，由生命周期任务对齐清理）。"""
    return f"lifecycle:hot:meta:{int(file_id)}"


def ttl_jittered(base: int = DEFAULT_CACHE_BASE_TTL, jitter_max: int = DEFAULT_CACHE_JITTER_MAX) -> int:
    """基础 TTL + 随机抖动，缓解同时过期。"""
    return int(base) + random.randint(0, int(jitter_max))


def _release_lock(redis: Redis, lock_key: str, token: str) -> None:
    lua = """
if redis.call("get", KEYS[1]) == ARGV[1] then
  return redis.call("del", KEYS[1])
else
  return 0
end
"""
    try:
        redis.eval(lua, 1, lock_key, token)
    except Exception:
        _log.warning("lock_release_lua_failed key=%s; NOT deleting to avoid removing another holder's lock", lock_key)


def read_through_json(
    redis: Redis,
    cache_key: str,
    compute: Callable[[], dict[str, Any]],
    *,
    base_ttl: int = DEFAULT_CACHE_BASE_TTL,
    jitter_max: int = DEFAULT_CACHE_JITTER_MAX,
    lock_ttl_sec: int = DEFAULT_LOCK_TTL_SEC,
    lock_wait_sec: float = DEFAULT_LOCK_WAIT_SEC,
) -> dict[str, Any]:
    """
    先读缓存；未命中则 SETNX 抢锁，仅持有者计算并写入；其它协程轮询等待。
    全程记录命中/未命中（由调用方传入 perf 钩子更佳；此处仅返回数据）。
    """
    from backend.core.perf_context import record_cache_hit, record_cache_miss

    raw = redis.get(cache_key)
    if raw is not None:
        try:
            result = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            _log.warning("corrupted_cache key=%s, deleting", cache_key)
            redis.delete(cache_key)
        else:
            record_cache_hit()
            return result

    record_cache_miss()
    lk = lock_key_for(cache_key)
    token = str(uuid.uuid4())
    acquired = bool(redis.set(lk, token, nx=True, ex=lock_ttl_sec))

    if acquired:
        try:
            raw2 = redis.get(cache_key)
            if raw2 is not None:
                record_cache_hit()
                return json.loads(raw2)
            data = compute()
            redis.setex(cache_key, ttl_jittered(base_ttl, jitter_max), json.dumps(data, default=str))
            return data
        finally:
            _release_lock(redis, lk, token)

    deadline = time.monotonic() + lock_wait_sec
    while time.monotonic() < deadline:
        time.sleep(DEFAULT_LOCK_POLL_SEC)
        raw3 = redis.get(cache_key)
        if raw3 is not None:
            try:
                result3 = json.loads(raw3)
            except (json.JSONDecodeError, TypeError):
                redis.delete(cache_key)
                continue
            record_cache_hit()
            return result3

    raw_final = redis.get(cache_key)
    if raw_final is not None:
        try:
            return json.loads(raw_final)
        except (json.JSONDecodeError, TypeError):
            pass

    _log.warning(
        "cache_lock_wait_timeout key=%s waited=%ss — single fallback compute (no cache write)",
        cache_key,
        lock_wait_sec,
    )
    return compute()


def cache_delete(redis: Redis, *keys: str) -> int:
    if not keys:
        return 0
    return int(redis.delete(*keys))


def invalidate_analyze_for_file(redis: Redis, user_id: int, resource_id: str) -> None:
    """数据变更后删除该资源下所有 analyze 类型缓存（防脏读）。"""
    types_ = ("stats", "preview", "anomaly", "clean", "clean_rows", "basic", "iforest", "graph", "mock")
    ks = [analyze_cache_key(t, user_id, resource_id) for t in types_]
    cache_delete(redis, *ks)
    for k in ks:
        redis.delete(lock_key_for(k))


def invalidate_files_list(redis: Redis, user_id: int) -> None:
    cache_delete(redis, files_list_cache_key(user_id))


def get_json(redis: Redis, key: str) -> dict[str, Any] | None:
    v = redis.get(key)
    if v is None:
        return None
    try:
        return json.loads(v)
    except (json.JSONDecodeError, TypeError):
        _log.warning("corrupted_json key=%s, deleting", key)
        redis.delete(key)
        return None


def set_json(redis: Redis, key: str, data: dict[str, Any], *, base_ttl: int = DEFAULT_CACHE_BASE_TTL) -> None:
    redis.setex(key, ttl_jittered(base_ttl, DEFAULT_CACHE_JITTER_MAX), json.dumps(data, default=str))


def user_profile_cache_key(user_id: int) -> str:
    """可选：用户信息短缓存。"""
    return f"user:profile:{user_id}"


# --- Online Feature Store（实时预测；TTL 可抖动）---
ONLINE_FEATURE_BASE_TTL = 3600
ONLINE_FEATURE_JITTER_MAX = 400


def online_features_key(user_id: int, entity_id: int, version: str) -> str:
    return f"online_feat:{user_id}:{entity_id}:{version}"


def set_online_features_json(
    redis: Redis,
    user_id: int,
    entity_id: int,
    version: str,
    payload: dict[str, Any],
) -> None:
    key = online_features_key(user_id, entity_id, version)
    redis.setex(
        key,
        ttl_jittered(ONLINE_FEATURE_BASE_TTL, ONLINE_FEATURE_JITTER_MAX),
        json.dumps(payload, default=str),
    )


def get_online_features_json(
    redis: Redis,
    user_id: int,
    entity_id: int,
    version: str,
) -> dict[str, Any] | None:
    key = online_features_key(user_id, entity_id, version)
    raw = redis.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        _log.warning("corrupted_online_feature key=%s, deleting", key)
        redis.delete(key)
        return None
