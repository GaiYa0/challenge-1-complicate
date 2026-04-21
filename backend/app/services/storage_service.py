"""
统一对象存储访问（raw / clean / feature 分层）。
API 层禁止直接调用 MinIO SDK，仅通过本模块 + file_service 编排。
"""

from __future__ import annotations

import os
from pathlib import Path

from minio import Minio
from sqlalchemy.orm import Session

from backend.core.config import ALLOWED_UPLOAD_EXTENSIONS, MAX_UPLOAD_BYTES
from backend.core.exceptions import ServiceError
from backend.core.tenant_access import resolve_file_for_read
from backend.core.transaction import transaction
from backend.infra import minio_client
from backend.model.enums import DataLayer
from backend.app.services import lifecycle_service
from backend.model.models import User
from backend.app.repositories import file_repo
from backend.app.schemas.file import FileUploadData


def _unique_logical_filename(
    client: Minio,
    bucket: str,
    user_id: int,
    dataset: str,
    version: str,
    safe_basename: str,
    layer: DataLayer = DataLayer.RAW,
) -> tuple[str, str]:
    """
    返回 (object_name, logical_filename)。
    logical_filename 为对象路径最后一段，与 DB.filename 一致，供 API 查询。
    """
    stem = Path(safe_basename).stem
    suffix = Path(safe_basename).suffix
    n = 0
    while True:
        logical = f"{stem}_{n}{suffix}" if n else safe_basename
        object_name = minio_client.build_object_name(
            user_id, dataset, version, logical, layer=layer.value
        )
        if not minio_client.object_exists(client, bucket, object_name):
            return object_name, logical
        n += 1


def _validate_upload(raw_filename: str, content: bytes) -> str:
    """文件名防路径穿越、扩展名白名单、大小上限。"""
    raw = raw_filename or ""
    if ".." in raw or raw.startswith("/"):
        raise ServiceError("invalid filename")
    base = os.path.basename(raw.replace("\\", "/"))
    if not base or ".." in base:
        raise ServiceError("invalid filename")
    suf = Path(base).suffix.lower()
    if suf not in ALLOWED_UPLOAD_EXTENSIONS:
        raise ServiceError(f"不支持的文件格式 ({suf})，仅支持 CSV / XLS / XLSX / JSON")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ServiceError("file too large")
    return base


def save_file(
    db: Session,
    client: Minio,
    user: User,
    raw_filename: str,
    content: bytes,
    *,
    dataset: str = "default",
    version: str = "v1",
    layer: DataLayer = DataLayer.RAW,
    expires_seconds: int = 3600,
) -> FileUploadData:
    """
    写入 MinIO + 元数据入库（单事务）；返回预签名下载 URL，不暴露真实 bucket 路径给前端业务字段
    （仅存库内；对外主入口为 presigned_url）。
    """
    safe_name = _validate_upload(raw_filename, content)

    bucket = minio_client.bucket_for_layer(layer.value)
    object_name, logical_name = _unique_logical_filename(
        client, bucket, user.id, dataset, version, safe_name, layer
    )

    minio_client.put_bytes(client, bucket, object_name, content)

    try:
        with transaction(db):
            file_repo.insert_file(
                db,
                user_id=user.id,
                filename=logical_name,
                bucket_name=bucket,
                object_name=object_name,
                version=version,
                dataset=dataset,
                data_layer=layer.value,
            )
    except Exception:
        minio_client.remove_object(client, bucket, object_name)
        raise

    url = minio_client.presigned_get_url(
        client, bucket, object_name, expires_seconds=expires_seconds
    )
    return FileUploadData(
        filename=logical_name,
        presigned_url=url,
        bucket_name=bucket,
        object_name=object_name,
        version=version,
        dataset=dataset,
        data_layer=layer.value,
    )


def read_file_bytes(
    db: Session,
    client: Minio,
    filename: str,
    user: User,
    *,
    redis=None,
) -> bytes:
    """按逻辑文件名读取对象字节；支持冷层 gzip，并在读取后刷新访问统计。"""
    row = resolve_file_for_read(db, user, filename)
    raw = lifecycle_service.read_object_bytes_for_row(client, row)
    out = lifecycle_service.decode_archive_to_csv_bytes(row, raw)
    lifecycle_service.touch_after_read(db, redis, row)
    return out


def get_presigned_url(
    db: Session,
    client: Minio,
    filename: str,
    user: User,
    *,
    expires_seconds: int = 3600,
) -> str:
    row = resolve_file_for_read(db, user, filename)
    return minio_client.presigned_get_url(
        client, row.bucket_name, row.object_name, expires_seconds=expires_seconds
    )


def delete_object_for_row(client: Minio, row) -> None:
    minio_client.remove_object(client, row.bucket_name, row.object_name)
    if getattr(row, "cold_object_name", None):
        cb = getattr(row, "cold_bucket_name", None) or minio_client.BUCKET_COLD
        minio_client.remove_object(client, cb, row.cold_object_name)


def presigned_for_row(client: Minio, row, *, expires_seconds: int = 3600) -> str:
    """列表场景按行生成预签名，避免仅用 filename 在管理员视角产生歧义。"""
    if (getattr(row, "lifecycle_tier", "") or "").lower() == "cold" and getattr(row, "cold_object_name", None):
        bucket = getattr(row, "cold_bucket_name", None) or minio_client.BUCKET_COLD
        return minio_client.presigned_get_url(
            client, bucket, row.cold_object_name, expires_seconds=expires_seconds
        )
    return minio_client.presigned_get_url(
        client, row.bucket_name, row.object_name, expires_seconds=expires_seconds
    )
