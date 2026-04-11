"""
MLOps：train_model（sklearn + Feature Store）、MinIO 存储、Model Registry、灰度预测与回滚。
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import pickle
from typing import Any

import numpy as np
import pandas as pd
from minio import Minio
from redis import Redis
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.exceptions import ServiceError
from backend.core.tenant_access import resolve_file_for_read
from backend.infra import minio_client as minio_ops
from backend.model.models import User
from backend.repository import feature_repo, model_registry_repo
from backend.core.transaction import transaction
from backend.schema.model_schema import ModelPredictData, ModelTrainResult
from backend.service import feature_service

_log = logging.getLogger(__name__)

_MODEL_SIG_PREFIX = "model-sig:"


def _sign_blob(blob: bytes) -> bytes:
    """HMAC-SHA256 签名模型二进制，密钥取自 JWT_SECRET（与模型桶写权限绑定）。"""
    secret = get_settings().JWT_SECRET.encode("utf-8")
    sig = hmac.new(secret, blob, hashlib.sha256).hexdigest().encode("utf-8")
    return sig


def _verify_blob(blob: bytes, expected_sig: bytes) -> bool:
    secret = get_settings().JWT_SECRET.encode("utf-8")
    actual = hmac.new(secret, blob, hashlib.sha256).hexdigest().encode("utf-8")
    return hmac.compare_digest(actual, expected_sig)


def _build_labels(X: np.ndarray) -> np.ndarray:
    """无外部标签时用可重复弱标签（首列相对中位数二分类），保证可算指标。"""
    if X.size == 0:
        return np.array([], dtype=int)
    col0 = X[:, 0]
    med = float(np.median(col0))
    return (col0 > med).astype(int)


def train_model(
    db: Session,
    minio: Minio,
    *,
    model_name: str,
    feature_version: str,
    tenant_user_id: int | None,
    actor_user_id: int | None = None,
) -> ModelTrainResult:
    """
    使用 Feature Store 指定 feature_version 训练 HistGradientBoostingClassifier；
    指标在 hold-out 上计算；模型写入 MinIO models/{model_name}/{version}/model.pkl；
    Registry 初始 status=deprecated（需再激活 / 灰度）。
    """
    if tenant_user_id is None:
        rows = feature_repo.list_rows_all_for_version(db, version=feature_version)
    else:
        rows = feature_repo.list_rows_for_tenant_and_version(
            db, tenant_user_id=tenant_user_id, version=feature_version
        )
    if not rows:
        raise ServiceError("no feature rows for training")

    samples = feature_repo.group_by_entity(rows)
    feat_df = pd.DataFrame(samples).replace({None: np.nan}).fillna(0.0)
    num_df = feat_df.select_dtypes(include=[np.integer, np.floating])
    if num_df.empty or len(num_df) == 0:
        raise ServiceError("no numeric features for training")

    X = num_df.to_numpy(dtype=float)
    y = _build_labels(X)
    if len(np.unique(y)) < 2:
        y = np.random.RandomState(42).randint(0, 2, size=len(X))

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y if len(np.unique(y)) > 1 else None
    )
    clf = HistGradientBoostingClassifier(max_depth=5, max_iter=80, random_state=42)
    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)
    acc = float(accuracy_score(y_test, y_pred))
    prec = float(precision_score(y_test, y_pred, average="binary", zero_division=0))
    recall = float(recall_score(y_test, y_pred, average="binary", zero_division=0))

    version = model_registry_repo.next_model_version(db, model_name=model_name)
    object_path = f"{model_name}/{version}/model.pkl"
    bundle: dict[str, Any] = {
        "model": clf,
        "columns": list(num_df.columns),
        "feature_version": feature_version,
        "model_name": model_name,
        "model_version": version,
    }
    blob = pickle.dumps(bundle, protocol=pickle.HIGHEST_PROTOCOL)
    sig = _sign_blob(blob)
    minio_ops.put_bytes(
        minio,
        minio_ops.BUCKET_MODELS,
        object_path,
        blob,
        content_type="application/octet-stream",
    )
    minio_ops.put_bytes(
        minio,
        minio_ops.BUCKET_MODELS,
        object_path + ".sig",
        sig,
        content_type="text/plain",
    )

    with transaction(db):
        registry_row = model_registry_repo.insert_registry(
            db,
            model_name=model_name,
            version=version,
            feature_version=feature_version,
            object_path=object_path,
            eval_accuracy=acc,
            eval_precision=prec,
            eval_recall=recall,
            status="deprecated",
            traffic_percent=100,
        )

    out = ModelTrainResult(
        model_name=model_name,
        model_version=version,
        feature_version=feature_version,
        eval_accuracy=acc,
        eval_precision=prec,
        eval_recall=recall,
        registry_id=registry_row.id,
        object_path=object_path,
        status=registry_row.status,
    )
    if get_settings().KAFKA_ENABLED:
        from backend.events.producer import publish_model_trained

        uid = int(actor_user_id) if actor_user_id is not None else int(tenant_user_id or 0)
        publish_model_trained(uid, model_name, version)
    return out


def load_model_bundle(minio: Minio, object_path: str) -> dict[str, Any]:
    raw = minio_ops.get_bytes(minio, minio_ops.BUCKET_MODELS, object_path)
    try:
        sig = minio_ops.get_bytes(minio, minio_ops.BUCKET_MODELS, object_path + ".sig")
        if not _verify_blob(raw, sig):
            raise ServiceError("model signature verification failed — refusing to load")
    except Exception as exc:
        if isinstance(exc, ServiceError):
            raise
        _log.warning("model_sig_missing path=%s — loading without verification (legacy model)", object_path)
    return pickle.loads(raw)  # noqa: S301


def _choose_registry_row(
    db: Session,
    *,
    model_name: str,
    user_id: int,
) -> Any:
    """灰度：存在 canary 且 stable_hash(user)%100 < traffic_percent 则走 canary，否则 active。"""
    canary = model_registry_repo.get_canary(db, model_name=model_name)
    active = model_registry_repo.get_active(db, model_name=model_name)
    h = int(hashlib.sha256(str(user_id).encode()).hexdigest(), 16) % 100
    if canary is not None and h < int(canary.traffic_percent or 0):
        return canary
    if active is not None:
        return active
    if canary is not None:
        return canary
    return None


def predict(
    db: Session,
    minio: Minio,
    redis: Redis,
    filename: str,
    user: User,
    *,
    model_name: str = "default",
) -> ModelPredictData:
    reg = _choose_registry_row(db, model_name=model_name, user_id=int(user.id))
    if reg is None:
        raise ServiceError("no deployable model for model_name")

    bundle = load_model_bundle(minio, reg.object_path)
    clf = bundle["model"]
    columns = list(bundle["columns"])
    feature_version = str(bundle.get("feature_version", reg.feature_version))

    file_row = resolve_file_for_read(db, user, filename)
    entity_id = int(file_row.id)
    feats = feature_service.get_features(db, redis, user, entity_id, feature_version)
    if not feats:
        raise ServiceError("features not found for entity/version")

    row = pd.DataFrame([feats]).replace({None: np.nan}).fillna(0.0)
    row = row.reindex(columns=columns, fill_value=0.0)
    X = row.to_numpy(dtype=float)
    pred = clf.predict(X)
    pdata = ModelPredictData(
        prediction=int(pred[0]),
        model_name=model_name,
        model_version=reg.version,
        registry_status=reg.status,
    )
    if get_settings().KAFKA_ENABLED:
        from backend.events.producer import publish_prediction_done

        publish_prediction_done(int(user.id), filename)
    return pdata


def activate_version(db: Session, *, model_name: str, version: str) -> None:
    """全量：仅一条 active。"""
    target = model_registry_repo.get_by_name_version(db, model_name=model_name, version=version)
    if target is None:
        raise ServiceError("model version not found")
    with transaction(db):
        model_registry_repo.deprecate_status_for_name(db, model_name=model_name, status="active")
        model_registry_repo.update_status(db, target.id, status="active", traffic_percent=100)


def set_canary(db: Session, *, model_name: str, version: str, traffic_percent: int = 10) -> None:
    """灰度发布：指定版本为 canary，traffic_percent 默认 10。"""
    if not 1 <= traffic_percent <= 99:
        raise ServiceError("traffic_percent must be 1..99 for canary")
    target = model_registry_repo.get_by_name_version(db, model_name=model_name, version=version)
    if target is None:
        raise ServiceError("model version not found")
    with transaction(db):
        model_registry_repo.deprecate_status_for_name(db, model_name=model_name, status="canary")
        model_registry_repo.update_status(
            db, target.id, status="canary", traffic_percent=traffic_percent
        )


def promote_canary_to_active(db: Session, *, model_name: str) -> None:
    """对比通过后：canary -> active，原 active deprecated。"""
    canary = model_registry_repo.get_canary(db, model_name=model_name)
    if canary is None:
        raise ServiceError("no canary to promote")
    with transaction(db):
        model_registry_repo.deprecate_status_for_name(db, model_name=model_name, status="active")
        model_registry_repo.update_status(db, canary.id, status="active", traffic_percent=100)


def rollback_to_version(db: Session, *, model_name: str, version: str) -> None:
    """回滚：将指定历史版本重新设为 active。"""
    activate_version(db, model_name=model_name, version=version)


def list_registry(db: Session, *, model_name: str) -> list:
    """列出某 model_name 下所有 Registry 记录（API 层调用，避免直接访问 repo）。"""
    return model_registry_repo.list_by_model_name(db, model_name=model_name)
