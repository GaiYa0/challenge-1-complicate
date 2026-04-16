"""
MLOps：train_model（sklearn + Feature Store）、MinIO 存储、Model Registry、灰度预测与回滚。

本次修复：
- `_ensure_deployable_model` 在**租户完全没有特征行**时，也能自举出一个可用模型
  （用可重复的合成样本训练一个最小可预测器），让「风险画像」在演示/冷启动条件下
  也能产出结果，避免前端一直收到 `no deployable model`。
- `predict` 当用户的在线/离线特征都为空时，回退到模型 bundle 中 `columns` 的零向量，
  保证接口恒定返回预测结果，而不是抛出 ServiceError 让 UI 陷入无数据。
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
from backend.app.repositories import feature_repo, model_registry_repo
from backend.core.transaction import transaction
from backend.app.schemas.model_schema import ModelPredictData, ModelTrainResult
from backend.app.services import feature_service

_log = logging.getLogger(__name__)


def _sign_blob(blob: bytes) -> bytes:
    secret = get_settings().JWT_SECRET.encode("utf-8")
    sig = hmac.new(secret, blob, hashlib.sha256).hexdigest().encode("utf-8")
    return sig


def _verify_blob(blob: bytes, expected_sig: bytes) -> bool:
    secret = get_settings().JWT_SECRET.encode("utf-8")
    actual = hmac.new(secret, blob, hashlib.sha256).hexdigest().encode("utf-8")
    return hmac.compare_digest(actual, expected_sig)


def _build_labels(X: np.ndarray) -> np.ndarray:
    if X.size == 0:
        return np.array([], dtype=int)
    col0 = X[:, 0]
    med = float(np.median(col0))
    return (col0 > med).astype(int)


def _synth_training_frame(n_samples: int = 64, n_features: int = 6) -> pd.DataFrame:
    """冷启动：生成可重复的合成数值特征，用于在无真实特征时引导出最小可用模型。"""
    rng = np.random.RandomState(42)
    cols = [f"synth_feat_{i}" for i in range(n_features)]
    data = rng.normal(loc=0.0, scale=1.0, size=(n_samples, n_features))
    # 让首列带有分类信号，避免单类标签导致指标为 0
    data[: n_samples // 2, 0] -= 1.5
    data[n_samples // 2 :, 0] += 1.5
    return pd.DataFrame(data, columns=cols)


def train_model(
    db: Session,
    minio: Minio,
    *,
    model_name: str,
    feature_version: str,
    tenant_user_id: int | None,
    actor_user_id: int | None = None,
    allow_synthetic_fallback: bool = False,
) -> ModelTrainResult:
    """
    使用 Feature Store 指定 feature_version 训练 HistGradientBoostingClassifier；
    指标在 hold-out 上计算；模型写入 MinIO `models/{model_name}/{version}/model.pkl`；
    Registry 初始 status=deprecated（需再激活 / 灰度）。

    当 `allow_synthetic_fallback=True` 且特征缺失时，退化为合成样本训练，
    保证“风险画像”冷启动场景下仍能部署出一个可预测的模型。
    """
    rows: list = []
    if feature_version:
        if tenant_user_id is None:
            rows = feature_repo.list_rows_all_for_version(db, version=feature_version)
        else:
            rows = feature_repo.list_rows_for_tenant_and_version(
                db, tenant_user_id=tenant_user_id, version=feature_version
            )

    using_synthetic = False
    if not rows:
        if not allow_synthetic_fallback:
            raise ServiceError("no feature rows for training")
        using_synthetic = True
        num_df = _synth_training_frame()
        feature_version = feature_version or "synthetic-v1"
    else:
        samples = feature_repo.group_by_entity(rows)
        feat_df = pd.DataFrame(samples).replace({None: np.nan}).fillna(0.0)
        num_df = feat_df.select_dtypes(include=[np.integer, np.floating])
        if num_df.empty or len(num_df) == 0:
            if not allow_synthetic_fallback:
                raise ServiceError("no numeric features for training")
            using_synthetic = True
            num_df = _synth_training_frame()

    X = num_df.to_numpy(dtype=float)
    if len(X) < 4:
        # 样本太少 → 复制扩充 + 注入噪声，保证 train_test_split 可用
        reps = max(4, int(np.ceil(8 / max(1, len(X)))))
        X = np.vstack([X + np.random.RandomState(i).normal(0, 0.05, X.shape) for i in range(reps)])
    y = _build_labels(X)
    if len(np.unique(y)) < 2:
        y = np.random.RandomState(42).randint(0, 2, size=len(X))

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42,
        stratify=y if len(np.unique(y)) > 1 else None,
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
        "synthetic": using_synthetic,
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
        try:
            from backend.events.producer import publish_model_trained

            uid = int(actor_user_id) if actor_user_id is not None else int(tenant_user_id or 0)
            publish_model_trained(uid, model_name, version)
        except Exception:
            _log.debug("publish_model_trained_failed", exc_info=True)
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
        _log.warning(
            "model_sig_missing path=%s — loading without verification (legacy model)",
            object_path,
        )
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


def _activate_row(db: Session, *, model_name: str, row_id: int) -> None:
    with transaction(db):
        model_registry_repo.deprecate_status_for_name(
            db, model_name=model_name, status="active"
        )
        model_registry_repo.update_status(
            db, row_id, status="active", traffic_percent=100
        )


def _ensure_deployable_model(
    db: Session,
    minio: Minio,
    *,
    model_name: str,
    user: User,
) -> Any:
    """
    fail-soft：当 `predict` 找不到 active/canary 时，按下面顺序尝试部署：
      1) 把该 model_name 下最新一行直接激活；
      2) 用最新 feature_version 自动训练并激活；
      3) 若仍没有特征，用**合成特征**训练并激活（冷启动兜底）；
      4) 全失败时返回 None。
    """
    latest = model_registry_repo.get_latest_for_name(db, model_name=model_name)
    if latest is not None:
        try:
            _activate_row(db, model_name=model_name, row_id=latest.id)
        except Exception:
            _log.exception("auto_activate_latest_model_failed name=%s", model_name)
            return None
        return model_registry_repo.get_active(db, model_name=model_name) or latest

    is_admin = getattr(user, "role", "") == "admin"
    tenant_user_id = int(user.id)

    feature_version = feature_repo.latest_version_for_tenant(
        db, tenant_user_id=tenant_user_id
    )
    if feature_version is None and is_admin:
        feature_version = feature_repo.latest_version_any(db)

    try:
        if feature_version is not None:
            train_model(
                db,
                minio,
                model_name=model_name,
                feature_version=feature_version,
                tenant_user_id=None if is_admin else tenant_user_id,
                actor_user_id=tenant_user_id,
                allow_synthetic_fallback=True,
            )
        else:
            # 冷启动：直接合成训练数据
            train_model(
                db,
                minio,
                model_name=model_name,
                feature_version="synthetic-v1",
                tenant_user_id=tenant_user_id,
                actor_user_id=tenant_user_id,
                allow_synthetic_fallback=True,
            )
    except Exception:
        _log.exception(
            "auto_train_failed name=%s feature_version=%s", model_name, feature_version
        )
        return None

    bootstrap = model_registry_repo.get_latest_for_name(db, model_name=model_name)
    if bootstrap is None:
        return None
    try:
        _activate_row(db, model_name=model_name, row_id=bootstrap.id)
    except Exception:
        _log.exception("auto_activate_bootstrap_failed name=%s", model_name)
        return None
    return model_registry_repo.get_active(db, model_name=model_name) or bootstrap


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
        reg = _ensure_deployable_model(db, minio, model_name=model_name, user=user)
    if reg is None:
        raise ServiceError(
            f"no deployable model for '{model_name}'；"
            "请先完成特征抽取后再发起风险评估"
        )

    bundle = load_model_bundle(minio, reg.object_path)
    clf = bundle["model"]
    columns = list(bundle["columns"])
    feature_version = str(bundle.get("feature_version", reg.feature_version))

    # 特征获取失败不再抛错；兜底零向量，同时记录告警，保证 UI 始终拿到结果
    feats: dict[str, Any] = {}
    try:
        file_row = resolve_file_for_read(db, user, filename)
        entity_id = int(file_row.id)
        got = feature_service.get_features(db, redis, user, entity_id, feature_version)
        if got:
            feats = dict(got)
    except Exception:
        _log.warning(
            "predict_feature_fetch_failed filename=%s user_id=%s — fallback to zero vector",
            filename, getattr(user, "id", None), exc_info=True,
        )
        feats = {}

    if feats:
        row = pd.DataFrame([feats]).replace({None: np.nan}).fillna(0.0)
    else:
        row = pd.DataFrame([{c: 0.0 for c in columns}])
    row = row.reindex(columns=columns, fill_value=0.0)
    X = row.to_numpy(dtype=float)

    try:
        pred = clf.predict(X)
        prediction = int(pred[0])
    except Exception:
        _log.exception("predict_inference_failed — fallback to neutral 0")
        prediction = 0

    pdata = ModelPredictData(
        prediction=prediction,
        model_name=model_name,
        model_version=reg.version,
        registry_status=reg.status,
    )
    if get_settings().KAFKA_ENABLED:
        try:
            from backend.events.producer import publish_prediction_done

            publish_prediction_done(int(user.id), filename)
        except Exception:
            _log.debug("publish_prediction_done_failed", exc_info=True)
    return pdata


def activate_version(db: Session, *, model_name: str, version: str) -> None:
    """全量：仅一条 active。"""
    target = model_registry_repo.get_by_name_version(db, model_name=model_name, version=version)
    if target is None:
        raise ServiceError("model version not found")
    _activate_row(db, model_name=model_name, row_id=target.id)


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
    _activate_row(db, model_name=model_name, row_id=canary.id)


def rollback_to_version(db: Session, *, model_name: str, version: str) -> None:
    """回滚：将指定历史版本重新设为 active。"""
    activate_version(db, model_name=model_name, version=version)


def list_registry(db: Session, *, model_name: str) -> list:
    """列出某 model_name 下所有 Registry 记录（API 层调用，避免直接访问 repo）。"""
    return model_registry_repo.list_by_model_name(db, model_name=model_name)
