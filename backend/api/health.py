"""
API 层 —— 健康检查 / 测试路由
职责：只处理 HTTP；统一 success_for_request + 认证依赖。
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from neo4j import Driver
from redis import Redis

from backend.api.deps import get_current_user
from backend.core.deps import get_neo4j_driver, get_redis
from backend.model.models import User
from backend.schema.common import ApiResponse, success_for_request
from backend.schema.graph import GraphVisualizationData
from backend.schema.health import AnalysisDashboardData, HealthData, TestData
from backend.service import graph_service, health_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health", response_model=ApiResponse[HealthData])
def health(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
):
    return success_for_request(request, HealthData(status="ok"))


@router.get("/test", response_model=ApiResponse[TestData])
def test(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    redis: Annotated[Redis, Depends(get_redis)],
):
    data = health_service.get_test_data(redis)
    return success_for_request(request, data)


@router.get("/demo", response_model=ApiResponse[TestData])
def demo(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
):
    return success_for_request(request, TestData(msg="demo ok"))


@router.get("/analysis/dashboard", response_model=ApiResponse[AnalysisDashboardData])
def analysis_dashboard(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
):
    data = health_service.get_analysis_dashboard()
    return success_for_request(request, data)


@router.get("/analysis/graph", response_model=ApiResponse[GraphVisualizationData])
def analysis_graph(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    neo4j_driver: Driver = Depends(get_neo4j_driver),
    edge_limit: Annotated[int, Query(ge=1, le=5000, description="最多读取的 TRANSFER 边条数")] = 500,
):
    """
    分析页关系图：从 Neo4j 读取 User-[:TRANSFER]->User，供前端 G6 渲染。
    读库失败时返回空图，避免整页 500。
    """
    try:
        data = graph_service.build_visualization_data(neo4j_driver, edge_limit=edge_limit)
    except Exception:
        logger.exception("analysis_graph_neo4j_failed")
        data = GraphVisualizationData(nodes=[], edges=[])
    return success_for_request(request, data)
