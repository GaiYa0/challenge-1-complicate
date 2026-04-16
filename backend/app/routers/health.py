"""
API 层 —— 健康检查 / 测试路由
职责：只处理 HTTP；统一 success_for_request + 认证依赖。
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from neo4j import Driver
from redis import Redis
from starlette.concurrency import run_in_threadpool

from backend.app.routers.deps import get_current_user
from backend.core.config import get_settings
from backend.core.deps import get_neo4j_driver, get_redis
from backend.infra.redis_client import read_through_json
from backend.model.models import User
from backend.app.schemas.common import ApiResponse, success_for_request
from backend.app.schemas.analysis_viz import FundVizData, TripVizData
from backend.app.schemas.graph import GraphDegreeItem, GraphVisualizationData
from backend.app.schemas.health import AnalysisDashboardData, HealthData, TestData
from backend.app.services import analysis_viz_service, graph_service, health_service

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


@router.get("/analysis/fund", response_model=ApiResponse[FundVizData])
def analysis_fund_viz(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    neo4j_driver: Annotated[Driver, Depends(get_neo4j_driver)],
    edge_limit: Annotated[int, Query(ge=1, le=5000, description="TRANSFER 边条数上限")] = 500,
):
    """多维可视化 — 资金：交易/通话/异常时间线 + 有向资金流向图（边宽用金额）。"""
    try:
        data = analysis_viz_service.get_fund_viz_data(
            neo4j_driver, tenant_id=int(current_user.id), edge_limit=edge_limit
        )
    except Exception:
        logger.exception("analysis_fund_viz_failed")
        data = FundVizData(
            fund_events=[],
            call_events=[],
            anomaly_events=[],
            graph_nodes=[],
            graph_edges=[],
        )
    return success_for_request(request, data)


@router.get("/analysis/trip", response_model=ApiResponse[TripVizData])
def analysis_trip_viz(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """多维可视化 — 轨迹：出行点、时空伴随、网格聚合热力。"""
    data = analysis_viz_service.get_trip_viz_data()
    return success_for_request(request, data)


@router.get("/analysis/graph", response_model=ApiResponse[GraphVisualizationData])
async def analysis_graph(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    redis: Annotated[Redis, Depends(get_redis)],
    neo4j_driver: Annotated[Driver, Depends(get_neo4j_driver)],
    edge_limit: Annotated[int, Query(ge=1, le=5000, description="最多读取的 TRANSFER 边条数")] = 500,
):
    settings = get_settings()
    if settings.DEMO_MODE:
        return success_for_request(request, graph_service.demo_visualization_data())

    tid = int(current_user.id)
    cap = settings.GRAPH_NODE_CAP
    cache_key = f"graph:viz:{tid}:{edge_limit}:{cap}"

    def compute() -> dict:
        try:
            return graph_service.build_visualization_data(
                neo4j_driver,
                tenant_id=tid,
                edge_limit=edge_limit,
                node_cap=cap,
            ).model_dump(mode="json")
        except Exception:
            logger.exception("analysis_graph_neo4j_failed")
            return GraphVisualizationData(nodes=[], edges=[]).model_dump(mode="json")

    raw = await run_in_threadpool(
        lambda: read_through_json(
            redis,
            cache_key,
            compute,
            base_ttl=settings.GRAPH_VIZ_CACHE_TTL_SEC,
        )
    )
    return success_for_request(request, GraphVisualizationData.model_validate(raw))


@router.get("/analysis/degree", response_model=ApiResponse[list[GraphDegreeItem]])
async def analysis_degree(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    redis: Annotated[Redis, Depends(get_redis)],
    neo4j_driver: Annotated[Driver, Depends(get_neo4j_driver)],
):
    settings = get_settings()
    if settings.DEMO_MODE:
        viz = graph_service.demo_visualization_data()
        return success_for_request(request, graph_service.demo_out_degree_from_viz(viz))

    tid = int(current_user.id)
    cache_key = f"graph:degree:{tid}"

    def load() -> list[dict]:
        try:
            return [
                x.model_dump(mode="json")
                for x in graph_service.out_degree(neo4j_driver, tenant_id=tid)
            ]
        except Exception:
            logger.exception("analysis_degree_neo4j_failed")
            return []

    def compute() -> dict:
        return {"rows": load()}

    raw = await run_in_threadpool(
        lambda: read_through_json(
            redis,
            cache_key,
            compute,
            base_ttl=settings.GRAPH_VIZ_CACHE_TTL_SEC,
        )
    )
    rows = raw.get("rows") if isinstance(raw, dict) else []
    return success_for_request(
        request,
        [GraphDegreeItem.model_validate(x) for x in rows],
    )
