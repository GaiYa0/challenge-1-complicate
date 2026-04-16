"""
模型 HTTP 入口适配层：委托 ml_model_service（MLOps）。
"""

from minio import Minio
from redis import Redis
from sqlalchemy.orm import Session

from backend.core.exceptions import ForbiddenError
from backend.core.tenant_access import is_admin
from backend.model.models import User
from backend.app.schemas.model_schema import ModelPredictData, ModelTrainResult
from backend.app.services import ml_model_service


def train(
    db: Session,
    minio: Minio,
    user: User,
    *,
    model_name: str,
    feature_version: str,
    use_all_features: bool,
) -> ModelTrainResult:
    if use_all_features and not is_admin(user):
        raise ForbiddenError("use_all_features requires admin", code=40303)
    tenant_user_id = None if (use_all_features and is_admin(user)) else user.id
    return ml_model_service.train_model(
        db,
        minio,
        model_name=model_name,
        feature_version=feature_version,
        tenant_user_id=tenant_user_id,
        actor_user_id=user.id,
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
    return ml_model_service.predict(db, minio, redis, filename, user, model_name=model_name)
