"""
Service 层 —— 文件业务逻辑
职责：编排校验、统一存储、事务、Redis 读穿缓存（防击穿 + TTL 抖动）、失效。
"""

import json
import time
from io import BytesIO

import numpy as np
import pandas as pd
from minio import Minio
from redis import Redis
from sqlalchemy.orm import Session

from backend.core.exceptions import ServiceError
from backend.core.perf_context import add_db_time_ms
from backend.core.tenant_access import is_admin, resolve_file_for_read
from backend.core.transaction import transaction
from backend.infra.redis_client import (
    analyze_cache_key,
    files_list_cache_key,
    invalidate_analyze_for_file,
    invalidate_files_list,
    read_through_json,
)
from backend.model.models import User
from backend.repository import file_repo
from backend.schema.file import (
    AnomalyData,
    CleanData,
    ColumnStats,
    FileDetailItem,
    FileUploadData,
    PreviewData,
)
from backend.core.config import get_settings
from backend.service import storage_service


def file_owner_user_id_if_accessible(db: Session, filename: str, user: User) -> int | None:
    try:
        return int(resolve_file_for_read(db, user, filename).user_id)
    except ServiceError:
        return None


def _cache_partition_user_id(db: Session, filename: str, user: User) -> int:
    """缓存键中的 user_id 段：按文件行属主分区，避免同名跨租户串缓存。"""
    return int(resolve_file_for_read(db, user, filename).user_id)


def read_csv_as_dataframe(db: Session, minio: Minio, filename: str, user: User) -> pd.DataFrame:
    """供分析 / 特征 / 模型等 Service 复用。"""
    return _load_csv_df(db, minio, filename, user, redis=None)


def _load_csv_df(
    db: Session,
    minio: Minio,
    filename: str,
    user: User,
    *,
    redis: Redis | None,
) -> pd.DataFrame:
    resolve_file_for_read(db, user, filename)
    if not filename.lower().endswith(".csv"):
        raise ServiceError("only csv allowed for this operation")
    t0 = time.perf_counter()
    try:
        raw = storage_service.read_file_bytes(db, minio, filename, user, redis=redis)
        return pd.read_csv(BytesIO(raw))
    finally:
        add_db_time_ms((time.perf_counter() - t0) * 1000.0)


# ── 上传 ────────────────────────────────────────────

def upload_file(
    db: Session,
    minio: Minio,
    redis: Redis,
    user: User,
    raw_filename: str,
    content: bytes,
    *,
    dataset: str = "default",
    version: str = "v1",
) -> FileUploadData:
    out = storage_service.save_file(
        db, minio, user, raw_filename, content, dataset=dataset, version=version
    )
    invalidate_files_list(redis, user.id)
    invalidate_analyze_for_file(redis, user.id, out.filename)
    settings = get_settings()
    if settings.KAFKA_ENABLED:
        from backend.events.producer import publish_data_uploaded

        publish_data_uploaded(user.id, out.filename)
    elif settings.KAFKA_UPLOAD_FALLBACK_CELERY:
        from backend.tasks.clean_task import clean_data_task

        clean_data_task.delay(out.filename, user.id)
    return out


# ── 列表 ────────────────────────────────────────────

def list_filenames(db: Session, redis: Redis, user: User) -> list[str]:
    if is_admin(user):
        t0 = time.perf_counter()
        try:
            return file_repo.list_filenames_all(db)
        finally:
            add_db_time_ms((time.perf_counter() - t0) * 1000.0)

    uid = user.id
    key = files_list_cache_key(uid)

    def _compute() -> dict:
        t0 = time.perf_counter()
        try:
            names = file_repo.list_filenames_for_tenant(db, tenant_user_id=uid)
        finally:
            add_db_time_ms((time.perf_counter() - t0) * 1000.0)
        return {"items": names}

    return read_through_json(redis, key, _compute, base_ttl=120, jitter_max=40)["items"]


def list_files_detail(db: Session, minio: Minio, user: User) -> list[FileDetailItem]:
    t0 = time.perf_counter()
    try:
        if is_admin(user):
            rows = file_repo.list_files_all(db)
        else:
            rows = file_repo.list_files_for_tenant(db, tenant_user_id=user.id)
    finally:
        add_db_time_ms((time.perf_counter() - t0) * 1000.0)
    items: list[FileDetailItem] = []
    for r in rows:
        url = storage_service.presigned_for_row(minio, r)
        items.append(
            FileDetailItem(
                filename=r.filename,
                bucket_name=r.bucket_name,
                object_name=r.object_name,
                version=r.version,
                dataset=r.dataset,
                data_layer=r.data_layer,
                upload_time=r.created_at.isoformat() if r.created_at else None,
                presigned_url=url,
                lifecycle_tier=getattr(r, "lifecycle_tier", None),
                archive_format=getattr(r, "archive_format", None),
                warm_month_key=getattr(r, "warm_month_key", None),
            )
        )
    return items


# ── 删除（按 ID）────────────────────────────────────

def delete_file_by_id(db: Session, minio: Minio, redis: Redis, file_id: int, user: User) -> None:
    if is_admin(user):
        rec = file_repo.get_file_by_id_any(db, file_id)
    else:
        rec = file_repo.get_file_by_id_for_tenant(db, file_id, user.id)
    if rec is None:
        raise ServiceError("not found")
    try:
        with transaction(db):
            file_repo.delete_file_by_id(db, file_id)
    except Exception:
        raise
    storage_service.delete_object_for_row(minio, rec)
    invalidate_analyze_for_file(redis, rec.user_id, rec.filename)
    invalidate_files_list(redis, rec.user_id)


# ── 删除（按文件名）──────────────────────────────────

def delete_file_by_name(db: Session, minio: Minio, redis: Redis, filename: str, user: User) -> None:
    if is_admin(user):
        rows = file_repo.list_files_by_filename_all_tenants(db, filename)
        if not rows:
            raise ServiceError("file not found")
        if len(rows) > 1:
            raise ServiceError("ambiguous filename for admin; use file id")
        rec = rows[0]
        try:
            with transaction(db):
                file_repo.delete_file_by_id(db, rec.id)
        except Exception:
            raise
    else:
        rec = file_repo.get_file_for_tenant(db, filename, user.id)
        if rec is None:
            raise ServiceError("file not found")
        try:
            with transaction(db):
                file_repo.delete_file_for_tenant_by_name(db, filename, user.id)
        except Exception:
            raise
    storage_service.delete_object_for_row(minio, rec)
    invalidate_analyze_for_file(redis, rec.user_id, rec.filename)
    invalidate_files_list(redis, rec.user_id)


# ── CSV 预览 ─────────────────────────────────────────

def preview_csv(db: Session, minio: Minio, redis: Redis, filename: str, user: User) -> PreviewData:
    part_uid = _cache_partition_user_id(db, filename, user)
    key = analyze_cache_key("preview", part_uid, filename)

    def _compute() -> dict:
        df = _load_csv_df(db, minio, filename, user, redis=redis)
        rows = json.loads(df.head(5).to_json(orient="records", date_format="iso"))
        dtypes = {str(c): str(t) for c, t in df.dtypes.items()}
        return PreviewData(
            columns=df.columns.tolist(),
            dtypes=dtypes,
            shape=[int(df.shape[0]), int(df.shape[1])],
            preview=rows,
        ).model_dump(mode="json")

    data = read_through_json(redis, key, _compute)
    return PreviewData.model_validate(data)


# ── 清洗 ────────────────────────────────────────────

def clean_csv(db: Session, minio: Minio, filename: str, user: User) -> CleanData:
    df = _load_csv_df(db, minio, filename, user, redis=None)
    before = int(len(df))
    cleaned = df.dropna()
    after = int(len(cleaned))
    return CleanData(before=before, after=after)


# ── 统计 ────────────────────────────────────────────

def stats_csv(db: Session, minio: Minio, redis: Redis, filename: str, user: User) -> dict[str, ColumnStats]:
    part_uid = _cache_partition_user_id(db, filename, user)
    key = analyze_cache_key("stats", part_uid, filename)

    def _compute() -> dict:
        df = _load_csv_df(db, minio, filename, user, redis=redis)
        num_df = df.select_dtypes(include=[np.integer, np.floating])

        def _v(v):
            return None if pd.isna(v) else float(v)

        result: dict[str, ColumnStats] = {}
        for col in num_df.columns:
            s = num_df[col]
            result[str(col)] = ColumnStats(mean=_v(s.mean()), max=_v(s.max()), min=_v(s.min()))
        return {k: v.model_dump() for k, v in result.items()}

    raw = read_through_json(redis, key, _compute)
    return {k: ColumnStats.model_validate(v) for k, v in raw.items()}


# ── 异常检测 ─────────────────────────────────────────

def anomaly_csv(db: Session, minio: Minio, redis: Redis, filename: str, user: User) -> AnomalyData:
    part_uid = _cache_partition_user_id(db, filename, user)
    key = analyze_cache_key("anomaly", part_uid, filename)

    def _compute() -> dict:
        df = _load_csv_df(db, minio, filename, user, redis=redis)
        num_df = df.select_dtypes(include=[np.integer, np.floating])
        anomaly_count = 0
        for col in num_df.columns:
            s = num_df[col]
            m, st = s.mean(), s.std()
            if pd.isna(m) or pd.isna(st) or st == 0:
                continue
            lower = float(m) - 2 * float(st)
            upper = float(m) + 2 * float(st)
            bad = s.notna() & ((s < lower) | (s > upper))
            anomaly_count += int(bad.sum())
        return AnomalyData(anomaly_count=anomaly_count).model_dump()

    return AnomalyData.model_validate(read_through_json(redis, key, _compute))
