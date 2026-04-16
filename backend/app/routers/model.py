"""
API 层 —— 模型路由（MLOps：训练、Registry、灰度、预测）。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from minio import Minio
from redis import Redis
from sqlalchemy.orm import Session

from backend.app.routers.deps import get_current_user
from backend.app.routers.rbac import require_role
from backend.core.deps import get_db, get_minio, get_redis
from backend.model.models import User
from backend.app.schemas.common import ApiResponse, success_for_request
from backend.app.schemas.model_schema import (
    CeleryTaskSubmitData,
    ModelCanaryIn,
    ModelPredictData,
    ModelRegistryOut,
    ModelTrainResult,
    ModelVersionIn,
)
from backend.app.services import ml_model_service, model_service
from backend.tasks.dispatch import submit_predict, submit_train_async
from backend.tasks.queue_config import QUEUE_HIGH, QUEUE_LOW

router = APIRouter(prefix="/model")


def _registry_row_out(r) -> ModelRegistryOut:
    return ModelRegistryOut(
        id=r.id,
        model_name=r.model_name,
        version=r.version,
        feature_version=r.feature_version,
        object_path=r.object_path,
        eval_accuracy=float(r.eval_accuracy),
        eval_precision=float(r.eval_precision),
        eval_recall=float(r.eval_recall),
        traffic_percent=int(r.traffic_percent or 100),
        status=r.status,
        created_at=r.created_at.isoformat() if r.created_at else None,
    )


@router.post("/train", response_model=ApiResponse[ModelTrainResult])
def model_train(
    request: Request,
    current_user: Annotated[User, Depends(require_role("admin", "user"))],
    db: Session = Depends(get_db),
    minio: Minio = Depends(get_minio),
    model_name: str = Query("default", min_length=1, max_length=128),
    feature_version: str = Query("v1", min_length=1, max_length=32),
    use_all_features: bool = Query(
        False,
        description="管理员：使用全租户该 feature_version 的特征训练",
    ),
):
    data = model_service.train(
        db,
        minio,
        current_user,
        model_name=model_name,
        feature_version=feature_version,
        use_all_features=use_all_features,
    )
    return success_for_request(request, data)


@router.post(
    "/predict-async/{filename}",
    response_model=ApiResponse[CeleryTaskSubmitData],
    summary="异步预测（高优先级队列 high_priority）",
)
def model_predict_async(
    request: Request,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    model_name: str = Query("default", min_length=1, max_length=128),
):
    ar = submit_predict(current_user.id, filename, model_name)
    return success_for_request(
        request,
        CeleryTaskSubmitData(task_id=ar.id, queue=QUEUE_HIGH, state=str(ar.state)),
    )


@router.post(
    "/train-async",
    response_model=ApiResponse[CeleryTaskSubmitData],
    summary="异步训练（低优先级队列 low_priority）",
)
def model_train_async(
    request: Request,
    current_user: Annotated[User, Depends(require_role("admin", "user"))],
    model_name: str = Query("default", min_length=1, max_length=128),
    feature_version: str = Query("v1", min_length=1, max_length=32),
    use_all_features: bool = Query(
        False,
        description="管理员：使用全租户该 feature_version 的特征训练",
    ),
):
    ar = submit_train_async(
        current_user.id,
        model_name=model_name,
        feature_version=feature_version,
        use_all_features=use_all_features,
    )
    return success_for_request(
        request,
        CeleryTaskSubmitData(task_id=ar.id, queue=QUEUE_LOW, state=str(ar.state)),
    )


@router.get("/predict/{filename}", response_model=ApiResponse[ModelPredictData])
def model_predict(
    request: Request,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    minio: Minio = Depends(get_minio),
    redis: Redis = Depends(get_redis),
    model_name: str = Query("default", min_length=1, max_length=128),
):
    data = model_service.predict(db, minio, redis, filename, current_user, model_name=model_name)
    return success_for_request(request, data)


@router.get("/registry", response_model=ApiResponse[list[ModelRegistryOut]])
def list_model_registry(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    model_name: str = Query("default", min_length=1, max_length=128),
):
    rows = ml_model_service.list_registry(db, model_name=model_name)
    return success_for_request(request, [_registry_row_out(r) for r in rows])


@router.post("/registry/activate", response_model=ApiResponse[None])
def registry_activate(
    request: Request,
    body: ModelVersionIn,
    current_user: Annotated[User, Depends(require_role("admin"))],
    db: Session = Depends(get_db),
):
    ml_model_service.activate_version(db, model_name=body.model_name, version=body.version)
    return success_for_request(request, None, msg="activated")


@router.post("/registry/canary", response_model=ApiResponse[None])
def registry_canary(
    request: Request,
    body: ModelCanaryIn,
    current_user: Annotated[User, Depends(require_role("admin"))],
    db: Session = Depends(get_db),
):
    ml_model_service.set_canary(
        db,
        model_name=body.model_name,
        version=body.version,
        traffic_percent=body.traffic_percent,
    )
    return success_for_request(request, None, msg="canary set")


@router.post("/registry/promote-canary", response_model=ApiResponse[None])
def registry_promote_canary(
    request: Request,
    current_user: Annotated[User, Depends(require_role("admin"))],
    db: Session = Depends(get_db),
    model_name: str = Query("default"),
):
    ml_model_service.promote_canary_to_active(db, model_name=model_name)
    return success_for_request(request, None, msg="canary promoted to active")


@router.post("/registry/rollback", response_model=ApiResponse[None])
def registry_rollback(
    request: Request,
    body: ModelVersionIn,
    current_user: Annotated[User, Depends(require_role("admin"))],
    db: Session = Depends(get_db),
):
    ml_model_service.rollback_to_version(db, model_name=body.model_name, version=body.version)
    return success_for_request(request, None, msg="rolled back")
