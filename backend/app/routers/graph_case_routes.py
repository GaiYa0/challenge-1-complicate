import hashlib
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from minio import Minio
from redis import Redis
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from backend.app.routers.deps import get_current_user
from backend.core.config import get_settings
from backend.core.deps import get_db, get_minio, get_redis
from backend.core.exceptions import AppError, ForbiddenError
from backend.core.response import success_for_request
from backend.core.tenant_access import is_admin
from backend.infra.redis_client import read_through_json
from backend.model.models import User
from backend.app.repositories import case_repo
from backend.app.schemas.common import ApiResponse
from backend.app.schemas.graph import GraphDegreeItem, GraphVisualizationData
from backend.app.schemas.graph_controlled import ControlledGraphData, MergedGraphData
from backend.app.services import case_graph_service

router = APIRouter(tags=["graph-case"])
logger = logging.getLogger(__name__)


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
    minio: Annotated[Minio, Depends(get_minio)],
    person_id: str | None = Query(None, description="中心人物，与资金流水 name 列一致"),
    depth: int = Query(1, ge=1, le=8),
    limit: int = Query(80, ge=1, le=100, description="子图节点上限（演示建议 ≤100）"),
    centrality: bool = Query(False, description="返回归一化 degree centrality"),
):
    row = _case_scope(db, current_user, case_id)
    tid = int(row.user_id)
    settings = get_settings()
    ph = hashlib.sha256((person_id or "").encode("utf-8")).hexdigest()[:16]
    sig = case_graph_service.case_graph_cache_signature(db, tid, case_id)
    cache_key = f"graph:case_tabular:{tid}:{case_id}:{sig}:{ph}:{depth}:{limit}:{int(centrality)}"

    def compute() -> dict:
        return case_graph_service.build_controlled_graph_for_case(
            db,
            minio,
            tenant_user_id=tid,
            case_id=case_id,
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


@router.get("/cases/graph", response_model=ApiResponse[MergedGraphData])
async def get_merged_cases_graph(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    minio: Annotated[Minio, Depends(get_minio)],
    case_ids: str = Query(..., description="逗号分隔的案件 ID 列表"),
    limit: int = Query(80, ge=1, le=200),
):
    """合并多案件图谱：同名节点合并，边保留 case_id 来源（均来自各案表格文件）。"""
    raw_ids = [int(x.strip()) for x in case_ids.split(",") if x.strip().isdigit()]
    if not raw_ids or len(raw_ids) > 10:
        raise AppError("请选择 1-10 个案件", code=42010, status_code=400)

    case_rows = []
    for cid in raw_ids:
        case_rows.append(_case_scope(db, current_user, cid))

    merged_node_map: dict[str, dict] = {}
    merged_edges: list[dict] = []
    edge_seen: set[tuple[str, str, int]] = set()
    ei = 0

    for row in case_rows:
        tid = int(row.user_id)

        def _compute(
            r=row,
            t=tid,
        ) -> dict:
            return case_graph_service.build_controlled_graph_for_case(
                db,
                minio,
                tenant_user_id=t,
                case_id=r.id,
                person_id=None,
                depth=1,
                limit=limit,
                include_centrality=False,
            )

        raw = await run_in_threadpool(_compute)
        sub = ControlledGraphData.model_validate(raw)

        for n in sub.nodes:
            if n.id not in merged_node_map:
                merged_node_map[n.id] = {
                    "id": n.id, "label": n.label, "type": n.type,
                    "degree": n.degree, "centrality": n.centrality,
                    "case_ids": [row.id],
                }
            else:
                if row.id not in merged_node_map[n.id]["case_ids"]:
                    merged_node_map[n.id]["case_ids"].append(row.id)
                if n.degree and (merged_node_map[n.id].get("degree") or 0) < n.degree:
                    merged_node_map[n.id]["degree"] = n.degree

        for e in sub.edges:
            trip = (e.source, e.target, row.id)
            if trip in edge_seen:
                continue
            edge_seen.add(trip)
            merged_edges.append({
                "id": f"me{ei}", "source": e.source, "target": e.target,
                "type": e.type, "weight": e.weight, "case_id": row.id,
            })
            ei += 1

    result = MergedGraphData(
        nodes=[
            {**v} for v in merged_node_map.values()
        ],
        edges=merged_edges,
        case_ids=raw_ids,
    )
    return success_for_request(request, result)


@router.get("/cases/{case_id}/analysis/graph", response_model=ApiResponse[GraphVisualizationData])
async def case_analysis_graph(
    request: Request,
    case_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    redis: Annotated[Redis, Depends(get_redis)],
    db: Annotated[Session, Depends(get_db)],
    minio: Annotated[Minio, Depends(get_minio)],
    edge_limit: Annotated[int, Query(ge=1, le=5000)] = 500,
):
    row = _case_scope(db, current_user, case_id)
    settings = get_settings()
    tid = int(row.user_id)
    cap = settings.GRAPH_NODE_CAP
    sig = case_graph_service.case_graph_cache_signature(db, tid, case_id)
    cache_key = f"graph:viz_tabular:{tid}:{case_id}:{sig}:{edge_limit}:{cap}"

    def compute() -> dict:
        try:
            return case_graph_service.build_visualization_for_case(
                db,
                minio,
                tenant_user_id=tid,
                case_id=case_id,
                edge_limit=edge_limit,
                node_cap=cap,
            ).model_dump(mode="json")
        except Exception:
            logger.exception("case_analysis_graph_csv_failed")
            return GraphVisualizationData(nodes=[], edges=[]).model_dump(mode="json")

    raw = await run_in_threadpool(
        lambda: read_through_json(
            redis, cache_key, compute,
            base_ttl=settings.GRAPH_VIZ_CACHE_TTL_SEC,
        )
    )
    return success_for_request(request, GraphVisualizationData.model_validate(raw))


@router.get("/cases/{case_id}/analysis/degree", response_model=ApiResponse[list[GraphDegreeItem]])
async def case_analysis_degree(
    request: Request,
    case_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    redis: Annotated[Redis, Depends(get_redis)],
    db: Annotated[Session, Depends(get_db)],
    minio: Annotated[Minio, Depends(get_minio)],
):
    row = _case_scope(db, current_user, case_id)
    settings = get_settings()
    tid = int(row.user_id)
    sig = case_graph_service.case_graph_cache_signature(db, tid, case_id)
    cache_key = f"graph:degree_tabular:{tid}:{case_id}:{sig}"

    def load() -> list[dict]:
        try:
            return [
                x.model_dump(mode="json")
                for x in case_graph_service.out_degree_for_case(
                    db, minio, tenant_user_id=tid, case_id=case_id
                )
            ]
        except Exception:
            logger.exception("case_analysis_degree_csv_failed")
            return []

    def compute() -> dict:
        return {"rows": load()}

    raw = await run_in_threadpool(
        lambda: read_through_json(
            redis, cache_key, compute,
            base_ttl=settings.GRAPH_VIZ_CACHE_TTL_SEC,
        )
    )
    rows = raw.get("rows") if isinstance(raw, dict) else []
    return success_for_request(
        request,
        [GraphDegreeItem.model_validate(x) for x in rows],
    )
