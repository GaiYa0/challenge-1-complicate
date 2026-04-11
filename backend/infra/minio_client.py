"""
MinIO 基础设施：bucket 规划、对象上传、预签名 URL。
业务层禁止直接 import minio SDK，应通过 storage_service 调用本模块函数。
"""

from __future__ import annotations

from datetime import timedelta
from typing import BinaryIO

from minio import Minio
from minio.error import S3Error

# --- 企业级 bucket 划分 ---
BUCKET_RAW = "raw-data"
BUCKET_PROCESSED = "processed-data"
BUCKET_MODELS = "models"
BUCKET_COLD = "cold-data"


def bucket_for_layer(layer: str) -> str:
    if layer == "raw":
        return BUCKET_RAW
    if layer == "clean":
        return BUCKET_PROCESSED
    if layer == "feature":
        return BUCKET_PROCESSED
    return BUCKET_RAW


def ensure_buckets(client: Minio) -> None:
    for name in (BUCKET_RAW, BUCKET_PROCESSED, BUCKET_MODELS, BUCKET_COLD):
        if not client.bucket_exists(name):
            client.make_bucket(name)


def build_object_name(
    user_id: int,
    dataset: str,
    version: str,
    filename: str,
    *,
    layer: str = "raw",
) -> str:
    """
    数据湖规范对象键：{layer}/{user_id}/{dataset}/{version}/{filename}
    layer: raw | clean | feature
    """
    from backend.infra import data_lake

    return data_lake.lake_object_key(layer, user_id, dataset, version, filename)


def put_bytes(
    client: Minio,
    bucket: str,
    object_name: str,
    data: bytes,
    content_type: str = "text/csv",
) -> None:
    from io import BytesIO

    bio: BinaryIO = BytesIO(data)
    size = len(data)
    client.put_object(bucket, object_name, bio, length=size, content_type=content_type)


def get_bytes(client: Minio, bucket: str, object_name: str) -> bytes:
    resp = client.get_object(bucket, object_name)
    try:
        return resp.read()
    finally:
        resp.close()
        resp.release_conn()


def remove_object(client: Minio, bucket: str, object_name: str) -> None:
    try:
        client.remove_object(bucket, object_name)
    except S3Error:
        pass


def presigned_get_url(
    client: Minio,
    bucket: str,
    object_name: str,
    *,
    expires_seconds: int = 3600,
) -> str:
    return client.presigned_get_object(
        bucket,
        object_name,
        expires=timedelta(seconds=expires_seconds),
    )


def object_exists(client: Minio, bucket: str, object_name: str) -> bool:
    try:
        client.stat_object(bucket, object_name)
        return True
    except S3Error:
        return False
