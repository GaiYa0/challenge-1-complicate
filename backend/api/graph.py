"""
API 层 —— 图谱路由
职责：只处理 HTTP，业务委托给 graph_service。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from neo4j import Driver

from backend.api.rbac import require_role
from backend.core.deps import get_neo4j_driver
from backend.model.models import User
from backend.schema.common import ApiResponse, success_for_request
from backend.schema.graph import GraphDegreeItem, GraphEdgeIn, GraphRelation, GraphUserNodeIn
from backend.service import graph_service

router = APIRouter(prefix="/graph")


@router.post("/node", response_model=ApiResponse[None])
def create_graph_user_node(
    request: Request,
    body: GraphUserNodeIn,
    current_user: Annotated[User, Depends(require_role("admin"))],
    neo4j_driver: Driver = Depends(get_neo4j_driver),
):
    graph_service.create_user_node(neo4j_driver, body.name)
    return success_for_request(request, None)


@router.post("/edge", response_model=ApiResponse[None])
def create_graph_edge(
    request: Request,
    body: GraphEdgeIn,
    current_user: Annotated[User, Depends(require_role("admin"))],
    neo4j_driver: Driver = Depends(get_neo4j_driver),
):
    graph_service.create_edge(neo4j_driver, body.from_user, body.to_user)
    return success_for_request(request, None)


@router.get("/relations", response_model=ApiResponse[list[GraphRelation]])
def list_graph_relations(
    request: Request,
    current_user: Annotated[User, Depends(require_role("admin"))],
    neo4j_driver: Driver = Depends(get_neo4j_driver),
):
    data = graph_service.list_relations(neo4j_driver)
    return success_for_request(request, data)


@router.get("/degree", response_model=ApiResponse[list[GraphDegreeItem]])
def graph_out_degree(
    request: Request,
    current_user: Annotated[User, Depends(require_role("admin"))],
    neo4j_driver: Driver = Depends(get_neo4j_driver),
):
    data = graph_service.out_degree(neo4j_driver)
    return success_for_request(request, data)
