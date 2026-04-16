import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from neo4j import Driver
from redis import Redis
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from backend.app.routers.deps import get_current_user
from backend.core.config import get_settings
from backend.core.deps import get_db, get_neo4j_driver, get_redis
from backend.core.exceptions import AppError, ForbiddenError
from backend.core.response import success_for_request
from backend.core.tenant_access import is_admin
from backend.infra.redis_client import read_through_json
from backend.model.models import User
from backend.app.repositories import case_repo
from backend.app.schemas.common import ApiResponse
from backend.app.schemas.graph_controlled import ControlledGraphData
from backend.app.services.graph_controlled_service import build_controlled_graph

router = APIRouter(tags=["graph-case"])


def _case_scope(db, user: User, case_id: int):
    row = case_repo.get_by_id(db, case_id)
    if row is None:
        raise AppError("案件不存在", code=42001, status_code=404)
    if not is_admin(user) and row.user_id != user.id:
        raise ForbiddenError("无权访问该案件", code=42002)
    return row


@router.get("/cases/{case_id}/graph", response_model=ApiResponse[ControlledGraphData])
async def get_case_graph(
    request: Request,
    case_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    redis: Annotated[Redis, Depends(get_redis)],
    db: Annotated[Session, Depends(get_db)],
    neo4j_driver: Annotated[Driver, Depends(get_neo4j_driver)],
    person_id: str | None = Query(None, description="中心人物，与 Neo4j User.name 一致"),
    depth: int = Query(1, ge=1, le=8),
    limit: int = Query(80, ge=1, le=100, description="子图节点上限（演示建议 ≤100）"),
    centrality: bool = Query(False, description="返回归一化 degree centrality"),
):
    row = _case_scope(db, current_user, case_id)
    tid = int(row.user_id)
    settings = get_settings()
    ph = hashlib.sha256((person_id or "").encode("utf-8")).hexdigest()[:16]
    cache_key = f"graph:case:{tid}:{case_id}:{ph}:{depth}:{limit}:{int(centrality)}"

    def compute() -> dict:
        return build_controlled_graph(
            neo4j_driver,
            tenant_id=tid,
            person_id=person_id,
            depth=depth,
            limit=min(limit, 100),
            include_centrality=centrality,
        )

    raw = await run_in_threadpool(
        lambda: read_through_json(
            redis,
            cache_key,
            compute,
            base_ttl=settings.GRAPH_VIZ_CACHE_TTL_SEC,
        )
    )
    return success_for_request(request, ControlledGraphData.model_validate(raw))
