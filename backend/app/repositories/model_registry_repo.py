"""
Model Registry 数据访问（ORM）。
"""

from __future__ import annotations

import re

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.model.models import ModelRegistry


def next_model_version(db: Session, *, model_name: str) -> str:
    q = select(ModelRegistry.version).where(ModelRegistry.model_name == model_name).distinct()
    versions = [str(r[0]) for r in db.execute(q).all()]
    max_n = 0
    for v in versions:
        m = re.match(r"^v(\d+)$", v.strip(), re.IGNORECASE)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"v{max_n + 1}"


def insert_registry(
    db: Session,
    *,
    model_name: str,
    version: str,
    feature_version: str,
    object_path: str,
    eval_accuracy: float,
    eval_precision: float,
    eval_recall: float,
    status: str = "deprecated",
    traffic_percent: int = 100,
) -> ModelRegistry:
    rec = ModelRegistry(
        model_name=model_name,
        version=version,
        feature_version=feature_version,
        object_path=object_path,
        eval_accuracy=eval_accuracy,
        eval_precision=eval_precision,
        eval_recall=eval_recall,
        traffic_percent=traffic_percent,
        status=status,
    )
    db.add(rec)
    db.flush()
    return rec


def get_by_name_version(db: Session, *, model_name: str, version: str) -> ModelRegistry | None:
    return db.scalars(
        select(ModelRegistry)
        .where(ModelRegistry.model_name == model_name, ModelRegistry.version == version)
        .limit(1)
    ).first()


def get_active(db: Session, *, model_name: str) -> ModelRegistry | None:
    return db.scalars(
        select(ModelRegistry)
        .where(ModelRegistry.model_name == model_name, ModelRegistry.status == "active")
        .limit(1)
    ).first()


def get_canary(db: Session, *, model_name: str) -> ModelRegistry | None:
    return db.scalars(
        select(ModelRegistry)
        .where(ModelRegistry.model_name == model_name, ModelRegistry.status == "canary")
        .limit(1)
    ).first()


def get_latest_for_name(db: Session, *, model_name: str) -> ModelRegistry | None:
    """按 created_at 倒序取最新的一条（不论 status），用于缺省激活。"""
    return db.scalars(
        select(ModelRegistry)
        .where(ModelRegistry.model_name == model_name)
        .order_by(ModelRegistry.created_at.desc())
        .limit(1)
    ).first()


def list_by_model_name(db: Session, *, model_name: str) -> list[ModelRegistry]:
    q = (
        select(ModelRegistry)
        .where(ModelRegistry.model_name == model_name)
        .order_by(ModelRegistry.created_at.desc())
    )
    return list(db.scalars(q).all())


def update_status(db: Session, rec_id: int, *, status: str, traffic_percent: int | None = None) -> None:
    vals: dict = {"status": status}
    if traffic_percent is not None:
        vals["traffic_percent"] = traffic_percent
    db.execute(update(ModelRegistry).where(ModelRegistry.id == rec_id).values(**vals))
    db.flush()


def deprecate_status_for_name(db: Session, *, model_name: str, status: str) -> None:
    """将某 model_name 下指定 status 的行全部标记为 deprecated。"""
    db.execute(
        update(ModelRegistry)
        .where(ModelRegistry.model_name == model_name, ModelRegistry.status == status)
        .values(status="deprecated", traffic_percent=100)
    )
    db.flush()
