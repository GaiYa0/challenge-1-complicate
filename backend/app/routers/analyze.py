"""
API 层 —— 分析路由（异步）：请求仅投递 Celery，立即返回 task_id。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.app.routers.deps import get_current_user
from backend.core.deps import get_db
from backend.model.models import User
from backend.app.schemas.common import ApiResponse, success_for_request
from backend.app.schemas.task import TaskEnqueueData
from backend.app.services import analyze_service, task_service

router = APIRouter(prefix="/analyze", tags=["analyze"])


@router.post("/mock/{filename}", response_model=ApiResponse[TaskEnqueueData])
def analyze_mock_job(
    request: Request,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    data = analyze_service.enqueue_analyze_job(db, "mock", filename, current_user)
    return success_for_request(request, data)


@router.post("/basic/{filename}", response_model=ApiResponse[TaskEnqueueData])
def analyze_basic_job(
    request: Request,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    data = analyze_service.enqueue_analyze_job(db, "basic", filename, current_user)
    return success_for_request(request, data)


@router.post("/iforest/{filename}", response_model=ApiResponse[TaskEnqueueData])
def analyze_iforest_job(
    request: Request,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    data = analyze_service.enqueue_analyze_job(db, "iforest", filename, current_user)
    return success_for_request(request, data)


@router.post("/graph/{filename}", response_model=ApiResponse[TaskEnqueueData])
def analyze_graph_job(
    request: Request,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    data = analyze_service.enqueue_analyze_job(db, "graph", filename, current_user)
    return success_for_request(request, data)


@router.post("/clean/{filename}", response_model=ApiResponse[TaskEnqueueData])
def analyze_clean_job(
    request: Request,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    data = task_service.enqueue_clean(db, filename, current_user)
    return success_for_request(request, data)


@router.post("/features/{filename}", response_model=ApiResponse[TaskEnqueueData])
def analyze_feature_job(
    request: Request,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    data = task_service.enqueue_feature_extract(db, filename, current_user)
    return success_for_request(request, data)
