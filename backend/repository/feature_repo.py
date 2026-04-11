"""
Repository 层 —— Feature Store（离线行存）；仅 ORM 参数绑定。
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.model.models import Feature


def next_feature_version(db: Session, *, user_id: int, entity_id: int) -> str:
    """同一 user + entity 下递增 v1 / v2 / v3 …"""
    q = select(Feature.version).where(Feature.user_id == user_id, Feature.entity_id == entity_id).distinct()
    versions = [str(r[0]) for r in db.execute(q).all()]
    max_n = 0
    for v in versions:
        m = re.match(r"^v(\d+)$", v.strip(), re.IGNORECASE)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"v{max_n + 1}"


def bulk_insert_features(
    db: Session,
    *,
    user_id: int,
    entity_id: int,
    version: str,
    features: dict[str, Any],
) -> None:
    for name, value in features.items():
        db.add(
            Feature(
                user_id=user_id,
                entity_id=entity_id,
                feature_name=str(name)[:256],
                feature_value=value,
                version=version,
            )
        )
    db.flush()


def get_features_dict(
    db: Session,
    *,
    user_id: int,
    entity_id: int,
    version: str,
) -> dict[str, Any]:
    """离线读取：name -> value（仅该租户行）。"""
    q = select(Feature).where(
        Feature.user_id == user_id,
        Feature.entity_id == entity_id,
        Feature.version == version,
    )
    rows = list(db.execute(q).scalars().all())
    return {r.feature_name: r.feature_value for r in rows}


def list_rows_for_tenant_and_version(db: Session, *, tenant_user_id: int, version: str) -> list[Feature]:
    q = (
        select(Feature)
        .where(Feature.user_id == tenant_user_id, Feature.version == version)
        .order_by(Feature.entity_id, Feature.feature_name)
    )
    return list(db.execute(q).scalars().all())


def list_rows_all_for_version(db: Session, *, version: str) -> list[Feature]:
    """管理员训练：指定版本下全库特征行。"""
    q = select(Feature).where(Feature.version == version).order_by(Feature.user_id, Feature.entity_id, Feature.feature_name)
    return list(db.execute(q).scalars().all())


def group_by_entity(rows: list[Feature]) -> list[dict[str, Any]]:
    """训练用：每个 entity 一条扁平 dict。"""
    m: dict[int, dict[str, Any]] = defaultdict(dict)
    for r in rows:
        m[r.entity_id][r.feature_name] = r.feature_value
    return list(m.values())
