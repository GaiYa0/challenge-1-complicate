"""
API 层 —— Feature 路由（异步投递特征提取任务）。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from redis import Redis
from sqlalchemy.orm import Session

from backend.app.routers.deps import get_current_user
from backend.core.deps import get_db, get_redis
from backend.model.models import User
from backend.app.schemas.common import ApiResponse, success_for_request
from backend.app.schemas.feature import FeatureMapData
from backend.app.schemas.task import TaskEnqueueData
from backend.app.services import feature_service, task_service

router = APIRouter(tags=["feature"])


@router.post("/feature/{filename}", response_model=ApiResponse[TaskEnqueueData])
def extract_features_job(
    request: Request,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    data = task_service.enqueue_feature_extract(db, filename, current_user)
    return success_for_request(request, data)


@router.get("/features/entity/{entity_id}", response_model=ApiResponse[FeatureMapData])
def get_features(
    request: Request,
    entity_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    version: str = Query("v1", min_length=1, max_length=32, description="Feature Store 版本"),
):
    feats = feature_service.get_features(db, redis, current_user, entity_id, version)
    return success_for_request(
        request,
        FeatureMapData(entity_id=entity_id, version=version, features=feats),
    )
