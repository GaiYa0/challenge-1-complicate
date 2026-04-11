"""
统一数据访问层（任务5）

- 对象数据：经 MinIO + DB 元数据行解析后读字节
- 特征：Feature Store（Redis 在线 + PostgreSQL 离线），委托 feature_service
"""

from __future__ import annotations

from minio import Minio
from redis import Redis
from sqlalchemy.orm import Session

from backend.infra import minio_client as mc
from backend.model.models import File, User
from backend.service import feature_service


def read_lake_bytes(client: Minio, row: File) -> bytes:
    """按 File 行读取数据湖对象（raw / clean / feature 任意层）。"""
    return mc.get_bytes(client, row.bucket_name, row.object_name)


def read_features_unified(
    db: Session,
    redis: Redis,
    user: User,
    entity_id: int,
    version: str,
) -> dict:
    """读取特征（在线优先，与训练/推理共用同一入口）。"""
    return feature_service.get_features(db, redis, user, entity_id, version)
