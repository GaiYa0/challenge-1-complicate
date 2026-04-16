"""
模型自动训练：Celery Beat 定时 + 反馈触发（与 ml_model_service 复用 train_model）。
"""

from __future__ import annotations

import logging

from backend.app.repositories import feedback_repo, user_repo
from backend.app.services.ml_model_service import train_model
from backend.tasks.celery_app import celery_app
from backend.tasks import runtime
from backend.tasks.task_base import QuotaTrackedTask

logger = logging.getLogger("tasks.model")


@celery_app.task(name="tasks.scheduled_retrain")
def scheduled_retrain_task(model_name: str = "default", feature_version: str = "v1") -> dict:
    """定时任务：全量特征空间重训（tenant_user_id=None）。"""
    logger.info("scheduled_retrain_task model_name=%s feature_version=%s", model_name, feature_version)
    mio = runtime.minio_client()
    db = runtime.open_session()
    try:
        out = train_model(
            db,
            mio,
            model_name=model_name,
            feature_version=feature_version,
            tenant_user_id=None,
        )
        return {
            "code": 0,
            "msg": "ok",
            "data": out.model_dump(mode="json"),
        }
    finally:
        db.close()


@celery_app.task(
    bind=True,
    base=QuotaTrackedTask,
    name="tasks.retrain_on_feedback",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    retry_backoff=True,
    retry_backoff_max=3600,
    retry_jitter=True,
)
def retrain_on_feedback_task(
    self,
    model_name: str = "default",
    feature_version: str = "v1",
    *,
    tenant_user_id: int | None = None,
) -> dict:
    """反馈闭环：异步重训（新 artifact 默认 deprecated，需人工/接口 promote）。"""
    logger.info(
        "retrain_on_feedback_task model_name=%s feature_version=%s tenant=%s retry=%s",
        model_name,
        feature_version,
        tenant_user_id,
        getattr(self.request, "retries", 0),
    )
    mio = runtime.minio_client()
    db = runtime.open_session()
    try:
        out = train_model(
            db,
            mio,
            model_name=model_name,
            feature_version=feature_version,
            tenant_user_id=tenant_user_id,
        )
        return {"code": 0, "msg": "ok", "data": out.model_dump(mode="json")}
    finally:
        db.close()


@celery_app.task(
    bind=True,
    base=QuotaTrackedTask,
    name="tasks.model_predict_task",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 5, "countdown": 5},
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def model_predict_task(
    self,
    user_id: int,
    filename: str,
    model_name: str = "default",
) -> dict:
    """在线预测：高优先级队列；与 HTTP 同步预测逻辑一致。"""
    logger.info(
        "model_predict_task user_id=%s filename=%s model=%s retry=%s",
        user_id,
        filename,
        model_name,
        getattr(self.request, "retries", 0),
    )
    db = runtime.open_session()
    try:
        user = user_repo.get_user_by_id(db, user_id)
        if user is None:
            return {"code": 1, "msg": "user not found", "data": None}
        mio = runtime.minio_client()
        rds = runtime.redis_client()
        from backend.app.services import ml_model_service

        pdata = ml_model_service.predict(db, mio, rds, filename, user, model_name=model_name)
        return {"code": 0, "msg": "ok", "data": pdata.model_dump(mode="json")}
    finally:
        db.close()


@celery_app.task(
    bind=True,
    base=QuotaTrackedTask,
    name="tasks.model_train_async_task",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2, "countdown": 120},
    retry_backoff=True,
    retry_backoff_max=3600,
    retry_jitter=True,
)
def model_train_async_task(
    self,
    user_id: int,
    model_name: str = "default",
    feature_version: str = "v1",
    use_all_features: bool = False,
) -> dict:
    """离线训练：低优先级队列。"""
    from backend.core.tenant_access import is_admin

    logger.info(
        "model_train_async_task user_id=%s model=%s fv=%s use_all=%s retry=%s",
        user_id,
        model_name,
        feature_version,
        use_all_features,
        getattr(self.request, "retries", 0),
    )
    db = runtime.open_session()
    try:
        user = user_repo.get_user_by_id(db, user_id)
        if user is None:
            return {"code": 1, "msg": "user not found", "data": None}
        if use_all_features and not is_admin(user):
            return {"code": 40303, "msg": "use_all_features requires admin", "data": None}
        mio = runtime.minio_client()
        tenant_user_id = None if (use_all_features and is_admin(user)) else user.id
        out = train_model(
            db,
            mio,
            model_name=model_name,
            feature_version=feature_version,
            tenant_user_id=tenant_user_id,
            actor_user_id=user.id,
        )
        return {"code": 0, "msg": "ok", "data": out.model_dump(mode="json")}
    finally:
        db.close()


@celery_app.task(name="tasks.check_feedback_retrain")
def check_feedback_retrain_task(
    model_name: str = "default",
    feature_version: str = "v1",
    threshold: int = 5,
) -> dict:
    """
    数据变化触发：若近期错误反馈达到阈值则投递 retrain_on_feedback_task。
    """
    db = runtime.open_session()
    try:
        n = feedback_repo.count_recent_incorrect(db, hours=24)
        if n < threshold:
            return {"code": 0, "msg": "below threshold", "data": {"count": n, "threshold": threshold}}
        retrain_on_feedback_task.delay(model_name, feature_version, tenant_user_id=None)
        return {"code": 0, "msg": "retrain enqueued", "data": {"count": n}}
    finally:
        db.close()
