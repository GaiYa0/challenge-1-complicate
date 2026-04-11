"""
文件生命周期：热 Redis / 温 PostgreSQL+标准桶 / 冷 MinIO 压缩对象。
"""

from __future__ import annotations

import gzip
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from minio import Minio
from redis import Redis
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.infra import minio_client as minio_ops
from backend.infra.redis_client import lifecycle_hot_meta_key, ttl_jittered
from backend.model.enums import ArchiveFormat, LifecycleTier
from backend.model.models import File

_log = logging.getLogger("lifecycle")


HOT_TTL_SECONDS = 7 * 24 * 3600


def touch_after_read(db: Session, redis: Redis | None, row: File) -> None:
    """读取后刷新访问统计；热层写入 Redis 元数据摘要。"""
    now = datetime.now(timezone.utc)
    row.last_accessed_at = now
    row.access_count = int(row.access_count or 0) + 1
    db.add(row)
    db.flush()

    if redis is None:
        return
    if (row.lifecycle_tier or "").lower() != LifecycleTier.HOT.value:
        return
    key = lifecycle_hot_meta_key(row.id)
    payload: dict[str, Any] = {
        "file_id": row.id,
        "filename": row.filename,
        "tier": row.lifecycle_tier,
        "bucket": row.bucket_name,
        "object": row.object_name,
        "updated_at": now.isoformat(),
    }
    redis.setex(key, ttl_jittered(HOT_TTL_SECONDS, 3600), json.dumps(payload, default=str))


def clear_hot_meta(redis: Redis, file_id: int) -> None:
    redis.delete(lifecycle_hot_meta_key(file_id))


def read_object_bytes_for_row(client: Minio, row: File) -> bytes:
    """按当前层级读取对象原始字节（冷层为压缩包字节）。"""
    if (row.lifecycle_tier or "").lower() == LifecycleTier.COLD.value and row.cold_object_name:
        bucket = row.cold_bucket_name or minio_ops.BUCKET_COLD
        return minio_ops.get_bytes(client, bucket, row.cold_object_name)
    return minio_ops.get_bytes(client, row.bucket_name, row.object_name)


def decode_archive_to_csv_bytes(row: File, raw: bytes) -> bytes:
    """将存储格式还原为 CSV 文本字节，供 pandas 读取。"""
    fmt = (row.archive_format or ArchiveFormat.NONE.value).lower()
    if fmt == ArchiveFormat.GZIP_CSV.value:
        return gzip.decompress(raw)
    if fmt == ArchiveFormat.PARQUET.value:
        try:
            import io

            import pandas as pd

            return pd.read_parquet(io.BytesIO(raw)).to_csv(index=False).encode("utf-8")
        except Exception:
            _log.warning("parquet_decode_failed file_id=%s fallback gzip", row.id)
            return gzip.decompress(raw)
    return raw


def archive_warm_row_to_cold(db: Session, client: Minio, redis: Redis | None, row: File) -> bool:
    """
    将 warm 行迁移到冷存储：gzip(csv) 写入 cold-data，更新元数据。
    返回是否成功。
    """
    if not row.filename.lower().endswith(".csv"):
        _log.info("skip_cold_non_csv file_id=%s name=%s", row.id, row.filename)
        return False
    settings = get_settings()
    raw = minio_ops.get_bytes(client, row.bucket_name, row.object_name)
    gz = gzip.compress(raw, compresslevel=6)
    cold_key = f"cold/{row.user_id}/{row.id}.csv.gz"
    minio_ops.put_bytes(
        client,
        minio_ops.BUCKET_COLD,
        cold_key,
        gz,
        content_type="application/gzip",
    )
    row.cold_bucket_name = minio_ops.BUCKET_COLD
    row.cold_object_name = cold_key
    row.archive_format = ArchiveFormat.GZIP_CSV.value
    row.lifecycle_tier = LifecycleTier.COLD.value
    db.add(row)
    db.flush()
    if redis is not None:
        clear_hot_meta(redis, row.id)
    if settings.LIFECYCLE_DELETE_WARM_AFTER_COLD:
        minio_ops.remove_object(client, row.bucket_name, row.object_name)
    return True
