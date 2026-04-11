"""
Feature Store 编排：离线写入 DB + 在线写入 Redis；对外提供 get_features 与 Celery 共用生成入口。
"""

from __future__ import annotations

from typing import Any

from minio import Minio
from redis import Redis
from sqlalchemy.orm import Session

from backend.core.exceptions import ServiceError
from backend.core.tenant_access import is_admin
from backend.core.transaction import transaction
from backend.model.models import User
from backend.repository import feature_repo, file_repo
from backend.data_platform import streaming as stream_hooks
from backend.infra.redis_client import get_online_features_json, set_online_features_json
from backend.service import feature_pipeline_service


def run_feature_generation(
    db: Session,
    minio: Minio,
    redis: Redis,
    *,
    user_id: int,
    entity_id: int,
) -> dict[str, Any]:
    """
    标准化流程：读 clean → 提特征 → 分配 version → 离线入库 + 在线 Redis。
    """
    df, file_row = feature_pipeline_service.read_clean_dataframe(
        db, minio, user_id=user_id, entity_id=entity_id
    )
    payload = feature_pipeline_service.extract_standard_features(df, file_row)
    version = feature_repo.next_feature_version(db, user_id=user_id, entity_id=entity_id)

    with transaction(db):
        feature_repo.bulk_insert_features(
            db,
            user_id=user_id,
            entity_id=entity_id,
            version=version,
            features=payload,
        )

    set_online_features_json(redis, user_id, entity_id, version, payload)
    stream_hooks.notify_feature_online(user_id=user_id, entity_id=entity_id, version=version)

    return {
        "version": version,
        "entity_id": entity_id,
        "user_id": user_id,
        "feature_count": len(payload),
    }


def get_features(
    db: Session,
    redis: Redis,
    user: User,
    entity_id: int,
    version: str,
) -> dict[str, Any]:
    """
    复用接口：优先读 Online（Redis），否则读 Offline（DB）。
    entity 必须对当前用户（或 admin）可见。
    """
    if is_admin(user):
        frow = file_repo.get_file_by_id_any(db, entity_id)
    else:
        frow = file_repo.get_file_by_id_for_tenant(db, entity_id, user.id)
    if frow is None:
        raise ServiceError("entity not found")

    owner_id = int(frow.user_id)
    online = get_online_features_json(redis, owner_id, entity_id, version)
    if online is not None:
        return dict(online)
    offline = feature_repo.get_features_dict(
        db, user_id=owner_id, entity_id=entity_id, version=version
    )
    return dict(offline)


def extract_features_sync(
    db: Session,
    minio: Minio,
    redis: Redis,
    user: User,
    entity_id: int,
) -> dict[str, Any]:
    """同步生成（HTTP 直连场景）；租户校验。"""
    if is_admin(user):
        row = file_repo.get_file_by_id_any(db, entity_id)
    else:
        row = file_repo.get_file_by_id_for_tenant(db, entity_id, user.id)
    if row is None:
        raise ServiceError("entity not found")
    return run_feature_generation(db, minio, redis, user_id=int(row.user_id), entity_id=entity_id)
