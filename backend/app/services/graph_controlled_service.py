from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from neo4j import Driver

from backend.app.schemas.graph_controlled import ControlledGraphData, ControlledGraphEdge, ControlledGraphNode
from backend.app.services.graph_service import person_name_exists


def _fetch_ego_edges(
    driver: Driver,
    *,
    tenant_id: int,
    center: str,
    depth: int,
    node_cap: int,
) -> list[tuple[str, str, float]]:
    """以 center 为圆心的多跳子图聚合：权值 = 同向 TRANSFER 金额合计（无 amount 时按 1 计）。"""
    cypher = (
        "MATCH (c:User {name:$name, tenant_id:$tid}) "
        "CALL apoc.path.subgraphAll(c, { "
        "    relationshipFilter: 'TRANSFER', "
        "    maxLevel: $depth, "
        "    filterStartNode: false, "
        "    limit: $cap "
        "}) YIELD relationships "
        "UNWIND relationships AS r "
        "WITH startNode(r) AS a, endNode(r) AS b, r "
        "WHERE a.tenant_id = $tid AND b.tenant_id = $tid "
        "RETURN a.name AS s, b.name AS t, sum(coalesce(r.amount, 1.0)) AS w "
        "LIMIT $elim"
    )
    fallback = (
        "MATCH p = (c:User {name:$name, tenant_id:$tid})-[:TRANSFER*1..%d]-(n:User {tenant_id:$tid}) "
        "WITH p LIMIT $cap "
        "UNWIND relationships(p) AS r "
        "WITH startNode(r) AS a, endNode(r) AS b, r "
        "WHERE a.tenant_id = $tid AND b.tenant_id = $tid "
        "RETURN a.name AS s, b.name AS t, sum(coalesce(r.amount, 1.0)) AS w "
        "LIMIT $elim"
    ) % int(depth)
    params = {
        "name": center,
        "tid": int(tenant_id),
        "depth": int(depth),
        "cap": int(node_cap) * 8,
        "elim": int(node_cap) * 8,
    }
    out: list[tuple[str, str, float]] = []
    with driver.session() as session:
        try:
            result = session.run(cypher, **params)
            for rec in result:
                s = str(rec["s"] or "").strip()
                t = str(rec["t"] or "").strip()
                if s and t:
                    out.append((s, t, float(rec["w"])))
        except Exception:
            out = []
        if not out:
            result = session.run(fallback, **params)
            for rec in result:
                s = str(rec["s"] or "").strip()
                t = str(rec["t"] or "").strip()
                if s and t:
                    out.append((s, t, float(rec["w"])))
    return out


def _fetch_top_weighted_edges(
    driver: Driver,
    *,
    tenant_id: int,
    node_cap: int,
) -> list[tuple[str, str, float]]:
    """按加权度 TopN 挑选节点，返回其诱导子图的有向边。"""
    cypher = (
        "MATCH (a:User {tenant_id:$tid})-[r:TRANSFER]->(b:User {tenant_id:$tid}) "
        "WITH a.name AS s, b.name AS t, sum(coalesce(r.amount, 1.0)) AS w "
        "WITH collect({s:s, t:t, w:w}) AS edges "
        "UNWIND edges AS e "
        "WITH edges, e "
        "WITH edges, [x IN edges WHERE x.s = e.s OR x.t = e.s | x.w] AS ws, e.s AS name "
        "WITH edges, name, reduce(acc = 0.0, v IN ws | acc + v) AS deg "
        "ORDER BY deg DESC "
        "WITH edges, collect(name)[0..$cap] AS names "
        "UNWIND edges AS e "
        "WITH e, names "
        "WHERE e.s IN names AND e.t IN names "
        "RETURN e.s AS s, e.t AS t, e.w AS w "
        "ORDER BY w DESC "
        "LIMIT $elim"
    )
    out: list[tuple[str, str, float]] = []
    with driver.session() as session:
        try:
            result = session.run(
                cypher, tid=int(tenant_id), cap=int(node_cap), elim=int(node_cap) * 4
            )
            for rec in result:
                s = str(rec["s"] or "").strip()
                t = str(rec["t"] or "").strip()
                if s and t:
                    out.append((s, t, float(rec["w"])))
        except Exception:
            out = []
    return out


def _undirected_adj(
    directed: list[tuple[str, str, float]],
) -> dict[str, list[tuple[str, float]]]:
    best: dict[tuple[str, str], float] = {}
    for s, t, w in directed:
        k1, k2 = (s, t), (t, s)
        best[k1] = max(best.get(k1, 0.0), w)
        best[k2] = max(best.get(k2, 0.0), w)
    adj: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for (s, t), w in best.items():
        adj[s].append((t, w))
    return adj


def _bfs_nodes(
    adj: dict[str, list[tuple[str, float]]],
    start: str,
    max_depth: int,
    node_cap: int,
) -> set[str]:
    if node_cap <= 0:
        return set()
    visited: dict[str, int] = {start: 0}
    q: deque[str] = deque([start])
    while q and len(visited) < node_cap:
        u = q.popleft()
        du = visited[u]
        if du >= max_depth:
            continue
        for v, _ in adj.get(u, []):
            if v in visited or len(visited) >= node_cap:
                continue
            visited[v] = du + 1
            q.append(v)
    return set(visited.keys())


def _induced_sorted(
    directed: list[tuple[str, str, float]],
    node_set: set[str],
) -> list[tuple[str, str, float]]:
    agg: dict[tuple[str, str], float] = {}
    for s, t, w in directed:
        if s not in node_set or t not in node_set or s == t:
            continue
        k = (s, t)
        agg[k] = max(agg.get(k, 0.0), w)
    rows = sorted(agg.items(), key=lambda x: x[1], reverse=True)
    return [(s, t, w) for (s, t), w in rows]


def _compute_degrees(edges: list[tuple[str, str, float]]) -> dict[str, int]:
    d: dict[str, int] = defaultdict(int)
    for s, t, _ in edges:
        d[s] += 1
        d[t] += 1
    return dict(d)


def _fetch_top_weighted_edges_from_list(
    edges: list[tuple[str, str, float]],
    *,
    node_cap: int,
) -> list[tuple[str, str, float]]:
    """与 Neo4j _fetch_top_weighted_edges 意图一致：优先保留高度节点诱导子图。"""
    if not edges:
        return []
    score: dict[str, float] = defaultdict(float)
    for s, t, w in edges:
        score[s] += float(w)
        score[t] += float(w)
    top_names = sorted(score.keys(), key=lambda x: score[x], reverse=True)[: max(1, node_cap)]
    names_set = set(top_names)
    out = [(s, t, w) for s, t, w in edges if s in names_set and t in names_set]
    return out[: max(4, node_cap * 4)]


def _reachable_nodes_from_edges(
    edges: list[tuple[str, str, float]],
    center: str,
    max_depth: int,
    max_expand: int,
) -> set[str]:
    adj: dict[str, list[str]] = defaultdict(list)
    for s, t, _ in edges:
        if s != t:
            adj[s].append(t)
    depth: dict[str, int] = {center: 0}
    q: deque[str] = deque([center])
    while q and len(depth) < max_expand:
        u = q.popleft()
        du = depth[u]
        if du >= max_depth:
            continue
        for v in adj.get(u, []):
            if v not in depth:
                depth[v] = du + 1
                q.append(v)
            elif depth[v] > du + 1:
                depth[v] = du + 1
                q.append(v)
    return set(depth.keys())


def build_controlled_from_directed_edges(
    directed: list[tuple[str, str, float]],
    *,
    person_id: str | None,
    depth_cap: int,
    node_cap: int,
    include_centrality: bool,
    driver: Driver | None = None,
    tenant_id: int | None = None,
) -> dict[str, Any]:
    """
    由已有有向边表构建受控图（与 build_controlled_graph 后半段一致）。
    driver/tenant_id 仅在 person_id 有值、子图为空且需 Neo4j 单点回退时使用。
    """
    if person_id is not None:
        pid = person_id.strip()
        reachable = _reachable_nodes_from_edges(
            directed, pid, max_depth=depth_cap, max_expand=node_cap * 8
        )
        sub = [(s, t, w) for s, t, w in directed if s in reachable and t in reachable]
        if not sub:
            if pid in {x for s, t, _ in directed for x in (s, t)}:
                cen = 1.0 if include_centrality else None
                return ControlledGraphData(
                    nodes=[
                        ControlledGraphNode(
                            id=pid,
                            label=pid,
                            type="person",
                            degree=0,
                            centrality=cen,
                        )
                    ],
                    edges=[],
                ).model_dump(mode="json")
            if driver is not None and tenant_id is not None and person_name_exists(
                driver, name=pid, tenant_id=tenant_id
            ):
                cen = 1.0 if include_centrality else None
                return ControlledGraphData(
                    nodes=[
                        ControlledGraphNode(
                            id=pid,
                            label=pid,
                            type="person",
                            degree=0,
                            centrality=cen,
                        )
                    ],
                    edges=[],
                ).model_dump(mode="json")
            return {"nodes": [], "edges": []}
        adj = _undirected_adj(sub)
        node_set = _bfs_nodes(adj, pid, depth_cap, node_cap)
        edge_rows = _induced_sorted(sub, node_set)
    else:
        sub = _fetch_top_weighted_edges_from_list(directed, node_cap=node_cap)
        if not sub:
            return {"nodes": [], "edges": []}
        node_set = set()
        for s, t, _ in sub:
            node_set.add(s)
            node_set.add(t)
            if len(node_set) >= node_cap:
                break
        edge_rows = _induced_sorted(sub, node_set)

    deg_map = _compute_degrees(edge_rows)
    max_deg = max(deg_map.values(), default=1)

    nodes_out: list[ControlledGraphNode] = []
    for nid in sorted(node_set):
        cen = None
        if include_centrality and max_deg > 0:
            cen = round(deg_map.get(nid, 0) / max_deg, 4)
        nodes_out.append(
            ControlledGraphNode(
                id=nid,
                label=nid,
                type="person",
                degree=deg_map.get(nid, 0),
                centrality=cen,
            )
        )

    edges_out: list[ControlledGraphEdge] = []
    for i, (s, t, w) in enumerate(edge_rows):
        edges_out.append(
            ControlledGraphEdge(
                id=f"e{i}",
                source=s,
                target=t,
                type="TRANSFER",
                weight=float(w),
            )
        )

    return ControlledGraphData(nodes=nodes_out, edges=edges_out).model_dump(mode="json")


def build_controlled_graph(
    driver: Driver,
    *,
    tenant_id: int,
    person_id: str | None,
    depth: int,
    limit: int,
    include_centrality: bool,
) -> dict[str, Any]:
    node_cap = max(1, min(limit, 100))
    depth_cap = max(1, min(depth, 8))

    if person_id is not None:
        directed = _fetch_ego_edges(
            driver,
            tenant_id=tenant_id,
            center=person_id,
            depth=depth_cap,
            node_cap=node_cap,
        )
        if not directed:
            if person_name_exists(driver, name=person_id, tenant_id=tenant_id):
                cen = 1.0 if include_centrality else None
                return ControlledGraphData(
                    nodes=[
                        ControlledGraphNode(
                            id=person_id,
                            label=person_id,
                            type="person",
                            degree=0,
                            centrality=cen,
                        )
                    ],
                    edges=[],
                ).model_dump(mode="json")
            return {"nodes": [], "edges": []}
        adj = _undirected_adj(directed)
        node_set = _bfs_nodes(adj, person_id, depth_cap, node_cap)
    else:
        directed = _fetch_top_weighted_edges(
            driver, tenant_id=tenant_id, node_cap=node_cap
        )
        if not directed:
            return {"nodes": [], "edges": []}
        node_set = set()
        for s, t, _ in directed:
            node_set.add(s)
            node_set.add(t)
            if len(node_set) >= node_cap:
                break

    edge_rows = _induced_sorted(directed, node_set)
    deg_map = _compute_degrees(edge_rows)
    max_deg = max(deg_map.values(), default=1)

    nodes_out: list[ControlledGraphNode] = []
    for nid in sorted(node_set):
        cen = None
        if include_centrality and max_deg > 0:
            cen = round(deg_map.get(nid, 0) / max_deg, 4)
        nodes_out.append(
            ControlledGraphNode(
                id=nid,
                label=nid,
                type="person",
                degree=deg_map.get(nid, 0),
                centrality=cen,
            )
        )

    edges_out: list[ControlledGraphEdge] = []
    for i, (s, t, w) in enumerate(edge_rows):
        edges_out.append(
            ControlledGraphEdge(
                id=f"e{i}",
                source=s,
                target=t,
                type="TRANSFER",
                weight=float(w),
            )
        )

    return ControlledGraphData(nodes=nodes_out, edges=edges_out).model_dump(mode="json")
