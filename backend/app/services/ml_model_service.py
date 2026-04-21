"""
MLOps：train_model（sklearn + Feature Store）、MinIO 存储、Model Registry、灰度预测与回滚。

设计要点
- `_ensure_deployable_model` 在**租户完全没有特征行**时不会在请求线程里做训练；
  而是把训练扔到 Celery 低优先队列，当前请求返回一个**中性预测**（prediction=0），
  避免前端长时间 30s+ 卡住。冷启动标记用 Redis `model:bootstrap:{name}` setnx 去重。
- `predict` 结果加 Redis 短期缓存（默认 60s），键空间按
  `predict:{user_id}:{model_name}:{active_version or 0}:{sha1(filename)}`，避免同一份数据
  反复推理 / 模型文件从 MinIO 反复反序列化。
- 缓存未命中时，模型 bundle 在进程内 LRU，减少重复拉取；bundle 按
  `(model_name, version)` 唯一标识，模型激活变更会自动让下一次 predict 拿到新版本。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import pickle
import threading
from functools import lru_cache
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

PREDICT_CACHE_TTL_SEC = 60
BOOTSTRAP_LOCK_TTL_SEC = 300  # 冷启动并发去重 5 分钟
_BUNDLE_CACHE_LOCK = threading.Lock()


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


def _load_bundle_from_minio(minio: Minio, object_path: str) -> dict[str, Any]:
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


# 进程内 bundle 缓存：key=(model_name, version) → bundle。
# 容量 4 够用：同时使用的模型数量远小于此。
_BUNDLE_CACHE: "dict[tuple[str, str], dict[str, Any]]" = {}
_BUNDLE_CACHE_ORDER: list[tuple[str, str]] = []
_BUNDLE_CACHE_CAP = 4


def load_model_bundle(minio: Minio, object_path: str) -> dict[str, Any]:
    """保留兼容签名。业务内部请使用 `_get_bundle_cached`。"""
    return _load_bundle_from_minio(minio, object_path)


def _get_bundle_cached(
    minio: Minio, *, model_name: str, version: str, object_path: str
) -> dict[str, Any]:
    key = (str(model_name), str(version))
    with _BUNDLE_CACHE_LOCK:
        cached = _BUNDLE_CACHE.get(key)
        if cached is not None:
            return cached
    bundle = _load_bundle_from_minio(minio, object_path)
    with _BUNDLE_CACHE_LOCK:
        _BUNDLE_CACHE[key] = bundle
        _BUNDLE_CACHE_ORDER.append(key)
        while len(_BUNDLE_CACHE_ORDER) > _BUNDLE_CACHE_CAP:
            evict = _BUNDLE_CACHE_ORDER.pop(0)
            _BUNDLE_CACHE.pop(evict, None)
    return bundle


def _predict_cache_key(
    *, user_id: int, model_name: str, filename: str, version: str | None
) -> str:
    h = hashlib.sha1(filename.encode("utf-8", errors="replace")).hexdigest()[:16]
    v = version or "0"
    return f"predict:{int(user_id)}:{model_name}:{v}:{h}"


def _predict_cache_get(redis: Redis | None, key: str) -> dict[str, Any] | None:
    if redis is None:
        return None
    try:
        raw = redis.get(key)
        if not raw:
            return None
        return json.loads(raw)
    except Exception:
        _log.debug("predict_cache_get_failed key=%s", key, exc_info=True)
        return None


def _predict_cache_set(redis: Redis | None, key: str, data: dict[str, Any]) -> None:
    if redis is None:
        return
    try:
        redis.setex(key, PREDICT_CACHE_TTL_SEC, json.dumps(data, default=str))
    except Exception:
        _log.debug("predict_cache_set_failed key=%s", key, exc_info=True)


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
    # 进程内 bundle 缓存也要失效，防止灰度/回滚后还取到旧版本
    with _BUNDLE_CACHE_LOCK:
        stale = [k for k in _BUNDLE_CACHE if k[0] == model_name]
        for k in stale:
            _BUNDLE_CACHE.pop(k, None)
        _BUNDLE_CACHE_ORDER[:] = [k for k in _BUNDLE_CACHE_ORDER if k[0] != model_name]


def _try_enqueue_async_training(
    *,
    model_name: str,
    tenant_user_id: int,
    feature_version: str,
    redis: Redis | None,
) -> bool:
    """冷启动：向 low_priority 队列扔一次训练任务，并用 Redis setnx 去重，
    防止同一租户在短时间内反复入队。失败时静默，调用方继续兜底。"""
    lock_key = f"model:bootstrap:{model_name}:{tenant_user_id}"
    try:
        if redis is not None:
            acquired = redis.set(lock_key, "1", ex=BOOTSTRAP_LOCK_TTL_SEC, nx=True)
            if not acquired:
                _log.info(
                    "bootstrap_training_already_queued name=%s user=%s",
                    model_name, tenant_user_id,
                )
                return False
    except Exception:
        _log.debug("bootstrap_lock_acquire_failed", exc_info=True)

    try:
        from backend.tasks.dispatch import submit_train_async

        submit_train_async(
            user_id=int(tenant_user_id),
            model_name=model_name,
            feature_version=feature_version or "v1",
            use_all_features=False,
        )
        _log.info(
            "bootstrap_training_enqueued name=%s user=%s fv=%s",
            model_name, tenant_user_id, feature_version,
        )
        return True
    except Exception:
        _log.exception("bootstrap_training_enqueue_failed name=%s", model_name)
        return False


def _ensure_deployable_model(
    db: Session,
    minio: Minio,
    *,
    model_name: str,
    user: User,
    redis: Redis | None = None,
) -> Any:
    """
    fail-soft：当 `predict` 找不到 active/canary 时：
      1) 最新 registry 行存在 → 直接激活并返回；
      2) 最新行不存在 → **异步**（Celery low_priority）入队一次训练任务，
         当次请求返回 None 让 predict 走中性兜底，避免 HTTP 卡住。
    这样 UI 能立刻收到"中等风险 + 模型正在部署"提示；任务完成后下次请求就有真模型。
    """
    latest = model_registry_repo.get_latest_for_name(db, model_name=model_name)
    if latest is not None:
        try:
            _activate_row(db, model_name=model_name, row_id=latest.id)
        except Exception:
            _log.exception("auto_activate_latest_model_failed name=%s", model_name)
            return None
        return model_registry_repo.get_active(db, model_name=model_name) or latest

    tenant_user_id = int(user.id)
    feature_version = feature_repo.latest_version_for_tenant(
        db, tenant_user_id=tenant_user_id
    ) or "v1"
    _try_enqueue_async_training(
        model_name=model_name,
        tenant_user_id=tenant_user_id,
        feature_version=feature_version,
        redis=redis,
    )
    return None


def _neutral_prediction(model_name: str) -> ModelPredictData:
    """冷启动 / 推理失败时的中性结果。前端会把这类 note 呈现为 warning 而非 error。"""
    return ModelPredictData(
        prediction=0,
        model_name=model_name,
        model_version="pending",
        registry_status="bootstrapping",
    )


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
        reg = _ensure_deployable_model(
            db, minio, model_name=model_name, user=user, redis=redis
        )
    if reg is None:
        # 异步训练已在队列中：立即返回中性预测，UI 不阻塞
        return _neutral_prediction(model_name)

    cache_key = _predict_cache_key(
        user_id=int(user.id),
        model_name=model_name,
        filename=filename,
        version=str(getattr(reg, "version", "0")),
    )
    cached = _predict_cache_get(redis, cache_key)
    if cached is not None:
        try:
            return ModelPredictData.model_validate(cached)
        except Exception:
            _log.debug("predict_cache_hit_invalid key=%s", cache_key, exc_info=True)

    try:
        bundle = _get_bundle_cached(
            minio,
            model_name=model_name,
            version=str(reg.version),
            object_path=reg.object_path,
        )
    except Exception:
        _log.exception("load_bundle_failed — fallback to neutral")
        return _neutral_prediction(model_name)

    clf = bundle["model"]
    columns = list(bundle["columns"])
    feature_version = str(bundle.get("feature_version", reg.feature_version))

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
    _predict_cache_set(redis, cache_key, pdata.model_dump(mode="json"))

    if get_settings().KAFKA_ENABLED:
        try:
            from backend.events.producer import publish_prediction_done

            publish_prediction_done(int(user.id), filename)
        except Exception:
            _log.debug("publish_prediction_done_failed", exc_info=True)
    return pdata


def invalidate_predict_cache(
    redis: Redis | None, *, user_id: int | None = None, model_name: str | None = None
) -> int:
    """
    模型激活 / 灰度 / 回滚后调用，让旧的预测缓存尽快失效。
    返回清理的 key 数量；Redis 不可用时返回 0。
    """
    if redis is None:
        return 0
    pattern = f"predict:{user_id or '*'}:{model_name or '*'}:*"
    cleared = 0
    try:
        for key in redis.scan_iter(pattern, count=500):
            try:
                redis.delete(key)
                cleared += 1
            except Exception:
                continue
    except Exception:
        _log.debug("invalidate_predict_cache_scan_failed pattern=%s", pattern, exc_info=True)
    return cleared


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
