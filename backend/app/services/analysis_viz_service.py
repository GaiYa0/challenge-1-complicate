"""
多维可视化数据：资金（Neo4j 子图 + 合成时间线）、轨迹（示例/可换真实源）。
严格多租户：Neo4j 查询必须带 tenant_id。
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from neo4j import Driver

from backend.core.exceptions import ServiceError
from backend.app.schemas.analysis_viz import (
    FundGraphEdge,
    FundGraphNode,
    FundTimelineEvent,
    FundVizData,
    HeatmapCell,
    TripBounds,
    TripCoOccurrence,
    TripPoint,
    TripVizData,
)


def _stable_ts(base: datetime, s: str, t: str, idx: int) -> str:
    h = int(hashlib.md5(f"{s}|{t}|{idx}".encode()).hexdigest()[:6], 16)
    delta = timedelta(hours=(h % (24 * 30)), minutes=(h % 120))
    return (base + delta).replace(tzinfo=timezone.utc).isoformat()


def get_fund_viz_data(
    driver: Driver, *, tenant_id: int, edge_limit: int = 500
) -> FundVizData:
    """从 Neo4j 读取 TRANSFER，生成时间线与有向金额边（按租户严格隔离）。"""
    if tenant_id is None:
        raise ServiceError("tenant_id is required")
    tid = int(tenant_id)
    lim = max(1, min(int(edge_limit or 0), 5000))
    cypher = (
        "MATCH (a:User {tenant_id: $tid})-[r:TRANSFER]->(b:User {tenant_id: $tid}) "
        "RETURN a.name AS s, b.name AS t, sum(coalesce(r.amount, 1.0)) AS amt "
        "LIMIT $lim"
    )
    base = datetime.now(timezone.utc) - timedelta(days=30)

    fund_events: list[FundTimelineEvent] = []
    nodes: dict[str, str] = {}
    edges: list[FundGraphEdge] = []
    seen: set[tuple[str, str]] = set()

    with driver.session() as session:
        result = session.run(cypher, tid=tid, lim=lim)
        for idx, r in enumerate(result):
            s = str(r["s"] or "").strip()
            t = str(r["t"] or "").strip()
            if not s or not t:
                continue
            pair = (s, t)
            if pair in seen:
                continue
            seen.add(pair)
            nodes[s] = s
            nodes[t] = t
            amt = float(r["amt"] or 0.0)
            ts = _stable_ts(base, s, t, idx)
            fund_events.append(
                FundTimelineEvent(
                    ts=ts,
                    kind="fund",
                    label=f"转账 {amt:.0f}",
                    amount=amt,
                    from_party=s,
                    to_party=t,
                    meta={"edge_index": idx},
                )
            )
            edges.append(
                FundGraphEdge(
                    source=s,
                    target=t,
                    value=amt,
                    label=f"{amt:.0f}",
                )
            )

    node_list = sorted(nodes.keys())
    call_events: list[FundTimelineEvent] = []
    anomaly_events: list[FundTimelineEvent] = []

    n_call = min(12, len(node_list) * 2) if node_list else 0
    for i in range(n_call):
        a = node_list[i % len(node_list)]
        b = node_list[(i + 1) % len(node_list)]
        ts = (base + timedelta(hours=i * 50 + 3)).isoformat()
        call_events.append(
            FundTimelineEvent(
                ts=ts,
                kind="call",
                label="通话",
                from_party=a,
                to_party=b,
                meta={"duration_sec": 120 + i * 10},
            )
        )
    for i in range(min(5, len(edges))):
        e = edges[i]
        ts = (base + timedelta(days=i + 2, hours=4)).isoformat()
        anomaly_events.append(
            FundTimelineEvent(
                ts=ts,
                kind="anomaly",
                label="高频小额异常",
                amount=e.value,
                from_party=e.source,
                to_party=e.target,
                meta={"type": "high_freq_small"},
            )
        )

    graph_nodes = [
        FundGraphNode(id=k, name=v, category="account") for k, v in sorted(nodes.items())
    ]

    return FundVizData(
        fund_events=sorted(fund_events, key=lambda x: x.ts),
        call_events=sorted(call_events, key=lambda x: x.ts),
        anomaly_events=sorted(anomaly_events, key=lambda x: x.ts),
        graph_nodes=graph_nodes,
        graph_edges=edges,
    )


def _aggregate_heatmap(
    points: list[tuple[float, float, float]], cell_deg: float = 0.004
) -> list[HeatmapCell]:
    """简单网格聚合（度）→ 热力格。"""
    buckets: dict[tuple[int, int], float] = {}
    for lng, lat, w in points:
        gx = int(round(lng / cell_deg))
        gy = int(round(lat / cell_deg))
        buckets[(gx, gy)] = buckets.get((gx, gy), 0.0) + w
    out: list[HeatmapCell] = []
    for (gx, gy), v in buckets.items():
        lng = (gx + 0.5) * cell_deg
        lat = (gy + 0.5) * cell_deg
        out.append(HeatmapCell(lng=round(lng, 6), lat=round(lat, 6), value=v))
    return sorted(out, key=lambda c: -c.value)


def get_trip_viz_data() -> TripVizData:
    """轨迹 + 伴随 + 热力聚合（示例坐标：北京城区附近）。"""
    base_lat, base_lng = 39.9042, 116.4074
    pts_raw: list[TripPoint] = []
    for i in range(24):
        lat = base_lat + (i % 6 - 3) * 0.012 + (i % 3) * 0.002
        lng = base_lng + (i // 6 - 2) * 0.015 + (i % 4) * 0.001
        ts = (
            datetime.now(timezone.utc) - timedelta(hours=48 - i * 2)
        ).isoformat()
        pts_raw.append(
            TripPoint(
                person_id="P1" if i % 2 == 0 else "P2",
                lat=lat,
                lng=lng,
                ts=ts,
                weight=1.0 + (i % 5) * 0.2,
            )
        )

    co: list[TripCoOccurrence] = [
        TripCoOccurrence(
            person_a="P1",
            person_b="P2",
            lat=base_lat + 0.01,
            lng=base_lng + 0.01,
            ts=(datetime.now(timezone.utc) - timedelta(hours=10)).isoformat(),
            distance_m=120.0,
        ),
        TripCoOccurrence(
            person_a="P1",
            person_b="P2",
            lat=base_lat + 0.02,
            lng=base_lng + 0.018,
            ts=(datetime.now(timezone.utc) - timedelta(hours=8)).isoformat(),
            distance_m=95.0,
        ),
    ]

    heat_inputs: list[tuple[float, float, float]] = [
        (p.lng, p.lat, p.weight) for p in pts_raw
    ]
    for c in co:
        heat_inputs.append((c.lng, c.lat, 3.0))

    cells = _aggregate_heatmap(heat_inputs, cell_deg=0.003)

    lats = [p.lat for p in pts_raw] + [c.lat for c in co]
    lngs = [p.lng for p in pts_raw] + [c.lng for c in co]
    pad = 0.02
    bounds = TripBounds(
        min_lat=min(lats) - pad,
        max_lat=max(lats) + pad,
        min_lng=min(lngs) - pad,
        max_lng=max(lngs) + pad,
    )

    return TripVizData(
        points=pts_raw,
        co_occurrence=co,
        heatmap_cells=cells,
        bounds=bounds,
    )
