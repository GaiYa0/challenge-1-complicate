"""
人物画像：聚合经济 / 轨迹 / 社会关系子图 / 线索列表。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
from minio import Minio
from neo4j import Driver
from sqlalchemy.orm import Session

from backend.core.exceptions import AppError, ForbiddenError
from backend.core.tenant_access import is_admin
from backend.data_platform.risk_scoring_system import classify_risk_level
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
    PortraitFundLine,
    PortraitFundTxRow,
    PortraitSocial,
    TimelineBin,
)
from backend.app.services import case_graph_service, case_intel_service, clue_service, graph_service


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


def get_person_portrait(
    db: Session,
    neo4j: Driver,
    minio: Minio,
    *,
    user: User,
    case_id: int,
    person_id: str,
) -> PersonPortraitOut:
    case_row = _ensure_case(db, user, case_id)
    tid = int(case_row.user_id)
    pid = (person_id or "").strip()
    case_edges = case_graph_service.load_case_transfer_edges(
        db, minio, tenant_user_id=tid, case_id=case_id
    )
    in_case = pid in case_graph_service.node_set_from_edges(case_edges)
    in_neo = graph_service.person_name_exists(neo4j, name=pid, tenant_id=tid)
    if not in_case and not in_neo:
        raise AppError(
            "人物不在图谱中或 person_id 与本案表格构图 / Neo4j User.name 不一致",
            code=40401,
            status_code=404,
        )

    fund_only_flag = clue_service.case_tabular_is_fund_table_only(
        db,
        case_id=case_id,
        tenant_user_id=tid,
    )
    analytics = case_intel_service.run_case_analytics(
        db,
        minio,
        tenant_user_id=tid,
        case_id=case_id,
    )
    profile = case_intel_service.build_person_profile_from_case_analytics(pid, analytics)

    out_c, in_c = 0, 0
    tabular_amount: float | None = None
    if in_case:
        out_c, in_c = case_graph_service.transfer_counts_for_person(pid, case_edges)
        tabular_amount, _ = (
            case_graph_service.aggregate_tabular_amount_and_rows_for_person(
                db, minio, tenant_user_id=tid, case_id=case_id, person_id=person_id
            )
        )
        fund_lines_raw, fund_tx_rows_map, fund_time_bounds = (
            case_graph_service.aggregate_tabular_fund_lines_for_person(
                db, minio, tenant_user_id=tid, case_id=case_id, person_id=person_id
            )
        )
        soc = case_graph_service.ego_graph_visualization_from_edges(case_edges, pid)
        if tabular_amount is not None:
            econ_explain = (
                "资金总额来自本案可识别资金交易表的金额列（按用户侧字段汇总）；"
                "转出/转入条数来自表格构图；异常比例为高风险线索数占比。"
            )
        else:
            econ_explain = (
                "转出/转入条数来自本案导入表格（CSV/XLS/XLSX）构图；"
                "未解析到金额列或无法匹配用户侧时，总交易额为估算值；异常比例为高风险线索数占比。"
            )
    else:
        out_c, in_c = _neo_transfer_counts(neo4j, name=pid, tenant_id=tid)
        soc = _build_social_subgraph(neo4j, center=pid, tenant_id=tid)
        econ_explain = (
            "总交易额由 Neo4j 转出/转入边数结合稳定算法估算；异常比例为高风险线索数占比。"
        )
        fund_lines_raw = []
        fund_tx_rows_map: dict[str, list[tuple[float, str | None]]] = {}
        fund_time_bounds: dict[str, tuple[str | None, str | None]] = {}

    rows = clue_service._ensure_real_clues_if_empty(
        db,
        minio,
        case_id=case_id,
        person_id=person_id,
    )

    fund_df = analytics.get("fund_df")
    if in_case and tabular_amount is not None:
        total_amount = float(tabular_amount)
    else:
        if isinstance(fund_df, pd.DataFrame) and not fund_df.empty:
            person_rows = fund_df[
                (fund_df["from_account"].astype(str) == pid)
                | (fund_df["to_account"].astype(str) == pid)
            ]
            total_amount = float(person_rows["amount"].sum()) if not person_rows.empty else 0.0
        else:
            total_amount = 0.0
    if rows:
        high = sum(1 for r in rows if _cat(r.risk_level) == "high")
        anomaly_ratio = min(1.0, high / max(1, len(rows)))
        avg_risk = sum(float(r.risk_score) for r in rows) / len(rows)
    else:
        anomaly_ratio = 0.0
        avg_risk = 0.0

    risk_score = min(100.0, max(0.0, float(profile.get("risk_score") or avg_risk)))
    risk_level = str(profile.get("basic_info", {}).get("risk_level") or classify_risk_level(risk_score))

    trip = analytics.get("trip_df")
    map_points: list[MapPoint] = []
    if trip is not None and not trip.empty:
        for _, p in trip.iterrows():
            if str(p.get("person_id", "")).strip() == person_id:
                ts_raw = p.get("timestamp")
                try:
                    ts = pd.Timestamp(ts_raw).isoformat()
                except Exception:
                    ts = datetime.now(timezone.utc).isoformat()
                map_points.append(
                    MapPoint(
                        lat=float(p.get("lat")),
                        lng=float(p.get("lng")),
                        ts=ts,
                        label=f"轨迹 {p.get('person_id')}",
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
        beh_explain = "轨迹数据来自案件导入数据，时间分布按小时聚合。"
    else:
        timeline_bins = []
        beh_explain = "当前未检索到该对象的轨迹记录。"

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
            created_at=r.created_at.isoformat() if getattr(r, "created_at", None) else None,
        )
        for r in rows
    ]

    amt_src = (
        "可识别资金交易表金额列汇总"
        if in_case and tabular_amount is not None
        else "基于图谱边数估算"
    )
    summary = str(profile.get("summary") or (
        f"{person_id} 在本案中共 {len(rows)} 条线索；"
        f"资金往来相关规模约 {total_amount:,.0f} 元（{amt_src}）；"
        f"综合风险分约 {risk_score:.0f}（{risk_level}）。"
    ))

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
            explain=econ_explain,
            fund_only_evidence=fund_only_flag,
            fund_counterparty_lines=[
                PortraitFundLine(
                    counterparty=c,
                    amount=round(a, 2),
                    tx_count=n,
                    earliest_time=fund_time_bounds.get(c, (None, None))[0],
                    latest_time=fund_time_bounds.get(c, (None, None))[1],
                    rows=[
                        PortraitFundTxRow(
                            amount=round(amt, 2),
                            time=tstr,
                        )
                        for amt, tstr in fund_tx_rows_map.get(c, [])
                    ],
                )
                for c, a, n in fund_lines_raw
            ],
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
