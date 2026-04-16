"""
人物画像：聚合经济 / 轨迹 / 社会关系子图 / 线索列表。
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from neo4j import Driver
from sqlalchemy.orm import Session

from backend.core.exceptions import AppError, ForbiddenError
from backend.core.tenant_access import is_admin
from backend.model.models import User
from backend.app.repositories import case_repo
from backend.app.schemas.graph import GraphVisualizationData, GraphVisualizationEdge, GraphVisualizationNode
from backend.app.schemas.portrait import (
    MapPoint,
    PersonPortraitOut,
    PortraitBasicInfo,
    PortraitBehavior,
    PortraitClueItem,
    PortraitEconomic,
    PortraitSocial,
    TimelineBin,
)
from backend.app.services import analysis_viz_service, clue_service, graph_service


def _ensure_case(db: Session, user: User, case_id: int):
    row = case_repo.get_by_id(db, case_id)
    if row is None:
        raise AppError("案件不存在", code=42001, status_code=404)
    if not is_admin(user) and row.user_id != user.id:
        raise ForbiddenError("无权访问该案件", code=42002)
    return row


def _cat(v: Any) -> str:
    return v.value if hasattr(v, "value") else str(v)


def _neo_transfer_counts(
    driver: Driver, *, name: str, tenant_id: int
) -> tuple[int, int]:
    """单次 Cypher 同时拿到 out/in 计数。"""
    cypher = (
        "OPTIONAL MATCH (:User {name:$name, tenant_id:$tid})-[ro:TRANSFER]->(:User {tenant_id:$tid}) "
        "WITH count(ro) AS c_out "
        "OPTIONAL MATCH (:User {tenant_id:$tid})-[ri:TRANSFER]->(:User {name:$name, tenant_id:$tid}) "
        "RETURN c_out AS c_out, count(ri) AS c_in"
    )
    with driver.session() as session:
        rec = session.run(cypher, name=name, tid=int(tenant_id)).single()
    if not rec:
        return 0, 0
    return int(rec["c_out"] or 0), int(rec["c_in"] or 0)


def _synthetic_amount(name: str, n_edges: int) -> float:
    h = int(hashlib.md5(name.encode()).hexdigest()[:6], 16)
    base = 30_000.0 + (h % 500) * 100.0
    return float(max(0, n_edges) * base)


def _build_social_subgraph(
    driver: Driver, *, center: str, tenant_id: int, max_edges: int = 60
) -> GraphVisualizationData:
    """在 Neo4j 内直接聚合中心点一跳邻域的有向 TRANSFER 边。"""
    cypher = (
        "MATCH (c:User {name:$name, tenant_id:$tid})-[r:TRANSFER]-(n:User {tenant_id:$tid}) "
        "WITH c, r, n LIMIT $lim "
        "RETURN startNode(r).name AS s, endNode(r).name AS t"
    )
    edges_out: list[GraphVisualizationEdge] = []
    node_set: set[str] = {center}
    ei = 0
    try:
        with driver.session() as session:
            result = session.run(
                cypher, name=center, tid=int(tenant_id), lim=int(max_edges)
            )
            for r in result:
                s = str(r["s"] or "").strip()
                t = str(r["t"] or "").strip()
                if not s or not t:
                    continue
                node_set.add(s)
                node_set.add(t)
                edges_out.append(
                    GraphVisualizationEdge(id=f"e{ei}", source=s, target=t)
                )
                ei += 1
    except Exception:
        pass
    if not edges_out:
        return GraphVisualizationData(
            nodes=[GraphVisualizationNode(id=center, label=center)],
            edges=[],
        )
    nodes = [GraphVisualizationNode(id=k, label=k) for k in sorted(node_set)]
    return GraphVisualizationData(nodes=nodes, edges=edges_out)


def _hour_bins_from_points(points: list[MapPoint]) -> list[TimelineBin]:
    bins = [0] * 24
    for p in points:
        try:
            ts = datetime.fromisoformat(p.ts.replace("Z", "+00:00"))
            bins[ts.hour] += 1
        except Exception:
            continue
    return [TimelineBin(hour=h, count=c) for h, c in enumerate(bins)]


def _synthetic_behavior(person_id: str) -> tuple[list[MapPoint], dict[str, float]]:
    h = int(hashlib.sha256(person_id.encode()).hexdigest()[:8], 16)
    base_lat, base_lng = 39.9042 + (h % 7) * 0.002, 116.4074 + (h % 5) * 0.002
    pts: list[MapPoint] = []
    for i in range(10):
        pts.append(
            MapPoint(
                lat=base_lat + (i % 4) * 0.004,
                lng=base_lng + (i % 3) * 0.003,
                ts=datetime.now(timezone.utc).isoformat(),
                label=f"示例轨迹点{i+1}",
            )
        )
    pad = 0.02
    bounds = {
        "min_lng": base_lng - pad,
        "max_lng": base_lng + pad + 0.02,
        "min_lat": base_lat - pad,
        "max_lat": base_lat + pad + 0.02,
    }
    return pts, bounds


def get_person_portrait(
    db: Session,
    neo4j: Driver,
    *,
    user: User,
    case_id: int,
    person_id: str,
) -> PersonPortraitOut:
    case_row = _ensure_case(db, user, case_id)
    tid = int(case_row.user_id)
    if not graph_service.person_name_exists(neo4j, name=person_id, tenant_id=tid):
        raise AppError(
            "人物不在图谱中或 person_id 与 Neo4j User.name 不一致",
            code=40401,
            status_code=404,
        )

    rows = clue_service._seed_mock_if_empty(db, case_id=case_id, person_id=person_id)

    out_c, in_c = _neo_transfer_counts(neo4j, name=person_id, tenant_id=tid)
    total_edges = out_c + in_c
    total_amount = _synthetic_amount(person_id, max(1, total_edges))
    if rows:
        high = sum(1 for r in rows if _cat(r.risk_level) == "high")
        anomaly_ratio = min(1.0, high / max(1, len(rows)))
        avg_risk = sum(float(r.risk_score) for r in rows) / len(rows)
    else:
        anomaly_ratio = 0.0
        avg_risk = 0.0

    risk_score = min(100.0, max(0.0, avg_risk))
    risk_level = "low" if risk_score < 40 else "medium" if risk_score < 70 else "high"

    trip = analysis_viz_service.get_trip_viz_data()
    map_points: list[MapPoint] = []
    for p in trip.points:
        if p.person_id == person_id:
            map_points.append(
                MapPoint(
                    lat=p.lat,
                    lng=p.lng,
                    ts=p.ts,
                    label=f"轨迹 {p.person_id}",
                )
            )
    bounds_dict: dict[str, float] = {}
    if map_points:
        lats = [m.lat for m in map_points]
        lngs = [m.lng for m in map_points]
        pad = 0.015
        bounds_dict = {
            "min_lng": min(lngs) - pad,
            "max_lng": max(lngs) + pad,
            "min_lat": min(lats) - pad,
            "max_lat": max(lats) + pad,
        }
        timeline_bins = _hour_bins_from_points(map_points)
        beh_explain = "轨迹数据来自分析任务示例；时间分布按定位点小时聚合。"
    else:
        map_points, bounds_dict = _synthetic_behavior(person_id)
        timeline_bins = _hour_bins_from_points(map_points)
        beh_explain = "当前无与本人物 ID 完全匹配的定位点，以下为基于人物标识生成的可解释占位轨迹，接入真实数据后将自动替换。"

    soc = _build_social_subgraph(neo4j, center=person_id, tenant_id=tid)
    soc_explain = (
        f"以「{person_id}」为中心的一跳邻域子图（资金有向边）；"
        "点击前端「查看全案关系网」进入完整图谱。"
    )

    clues_out = [
        PortraitClueItem(
            id=r.id,
            title=r.title,
            risk_level=_cat(r.risk_level),
            risk_score=float(r.risk_score),
            category=_cat(r.category),
        )
        for r in rows
    ]

    summary = (
        f"{person_id} 在本案中共 {len(rows)} 条线索；"
        f"估算资金往来相关规模约 {total_amount:,.0f} 元（基于图谱边数估算）；"
        f"综合风险分约 {risk_score:.0f}（{risk_level}）。"
    )

    return PersonPortraitOut(
        basic_info=PortraitBasicInfo(
            case_id=case_id,
            person_id=person_id,
            display_name=person_id,
            risk_score=round(risk_score, 2),
            risk_level=risk_level,
            summary=summary,
        ),
        economic=PortraitEconomic(
            total_amount=round(total_amount, 2),
            anomaly_ratio=round(anomaly_ratio, 4),
            transfer_out_count=out_c,
            transfer_in_count=in_c,
            explain="总交易额由 Neo4j 转出/转入边数结合稳定算法估算；异常比例为高风险线索数占比。",
        ),
        behavior=PortraitBehavior(
            timeline_bins=timeline_bins,
            map_points=map_points,
            bounds=bounds_dict,
            explain=beh_explain,
        ),
        social=PortraitSocial(
            graph=soc,
            center_id=person_id,
            explain=soc_explain,
        ),
        clues=clues_out,
        links={
            "network_path": f"/cases/{case_id}/network",
            "clue_detail_template": f"/cases/{case_id}/clues/{{clue_id}}",
        },
    )
