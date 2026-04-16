"""
Service 层 —— 图谱业务逻辑
职责：封装 Neo4j 图操作的业务流程。严格多租户隔离 —— tenant_id 必填。
"""

from neo4j import Driver

from backend.core.exceptions import ServiceError
from backend.core.config import get_settings
from backend.app.schemas.graph import (
    GraphDegreeItem,
    GraphRelation,
    GraphVisualizationData,
    GraphVisualizationEdge,
    GraphVisualizationNode,
)


def _require_tid(tenant_id: int | None) -> int:
    if tenant_id is None:
        raise ServiceError("tenant_id is required for graph queries")
    return int(tenant_id)


def person_name_exists(driver: Driver, *, name: str, tenant_id: int) -> bool:
    tid = _require_tid(tenant_id)
    if not name:
        return False
    cypher = "MATCH (u:User {name: $name, tenant_id: $tid}) RETURN 1 AS x LIMIT 1"
    with driver.session() as session:
        rec = session.run(cypher, name=name, tid=tid).single()
        return rec is not None


def create_user_node(driver: Driver, name: str, *, tenant_id: int) -> None:
    tid = _require_tid(tenant_id)
    cypher = "MERGE (u:User {name: $name, tenant_id: $tid})"
    with driver.session() as session:
        session.run(cypher, name=name, tid=tid)


def create_edge(
    driver: Driver,
    from_user: str,
    to_user: str,
    *,
    tenant_id: int,
) -> None:
    tid = _require_tid(tenant_id)
    cypher = (
        "MATCH (a:User {name: $from_name, tenant_id: $tid}), "
        "(b:User {name: $to_name, tenant_id: $tid}) "
        "CREATE (a)-[:TRANSFER]->(b)"
    )
    with driver.session() as session:
        result = session.run(cypher, from_name=from_user, to_name=to_user, tid=tid)
        summary = result.consume()
        if summary.counters.relationships_created == 0:
            raise ServiceError("one or both users not found")


def list_relations(driver: Driver, *, tenant_id: int) -> list[GraphRelation]:
    tid = _require_tid(tenant_id)
    cypher = (
        "MATCH (a:User {tenant_id: $tid})-[:TRANSFER]->(b:User {tenant_id: $tid}) "
        "RETURN a.name AS from_name, b.name AS to_name"
    )
    with driver.session() as session:
        result = session.run(cypher, tid=tid)
        return [
            GraphRelation(from_user=r["from_name"], to_user=r["to_name"])
            for r in result
        ]


def demo_visualization_data() -> GraphVisualizationData:
    """演示模式：固定小规模链路与少量跨边，节点数 ≤ GRAPH_NODE_CAP。"""
    cap = max(10, min(get_settings().GRAPH_NODE_CAP, 100))
    n = min(28, cap)
    names = [f"演示{nid:02d}" for nid in range(1, n + 1)]
    nodes = [GraphVisualizationNode(id=x, label=x) for x in names]
    edges: list[GraphVisualizationEdge] = []
    ei = 0
    for i in range(n - 1):
        edges.append(
            GraphVisualizationEdge(id=f"e{ei}", source=names[i], target=names[i + 1])
        )
        ei += 1
    if n > 8:
        edges.append(GraphVisualizationEdge(id=f"e{ei}", source=names[0], target=names[7]))
        ei += 1
    if n > 16:
        edges.append(GraphVisualizationEdge(id=f"e{ei}", source=names[5], target=names[16]))
    return GraphVisualizationData(nodes=nodes, edges=edges)


def demo_out_degree_from_viz(data: GraphVisualizationData) -> list[GraphDegreeItem]:
    out: dict[str, int] = {}
    for e in data.edges:
        out[e.source] = out.get(e.source, 0) + 1
    ranked = sorted(out.items(), key=lambda x: (-x[1], x[0]))
    return [GraphDegreeItem(name=k, degree=v) for k, v in ranked]


def _clip_graph_by_node_cap(
    data: GraphVisualizationData, node_cap: int
) -> GraphVisualizationData:
    if len(data.nodes) <= node_cap:
        return data
    kept_ids = {n.id for n in data.nodes[:node_cap]}
    edges2 = [
        e
        for e in data.edges
        if e.source in kept_ids and e.target in kept_ids
    ]
    return GraphVisualizationData(nodes=data.nodes[:node_cap], edges=edges2)


def build_visualization_data(
    driver: Driver,
    *,
    tenant_id: int,
    edge_limit: int = 500,
    node_cap: int | None = None,
) -> GraphVisualizationData:
    """读取 User-[:TRANSFER]->User 边（同租户内），组装为前端 G6 可用的 nodes/edges。"""
    tid = _require_tid(tenant_id)
    if node_cap is None:
        node_cap = get_settings().GRAPH_NODE_CAP
    lim = max(1, min(int(edge_limit or 0), 5000))
    cypher = (
        "MATCH (a:User {tenant_id: $tid})-[r:TRANSFER]->(b:User {tenant_id: $tid}) "
        "RETURN a.name AS s, b.name AS t "
        "LIMIT $lim"
    )
    params: dict = {"tid": tid, "lim": lim}

    node_map: dict[str, str] = {}
    edges_out: list[GraphVisualizationEdge] = []
    seen_pairs: set[tuple[str, str]] = set()
    ei = 0

    with driver.session() as session:
        result = session.run(cypher, **params)
        for r in result:
            s = str(r["s"] or "").strip()
            t = str(r["t"] or "").strip()
            if not s or not t:
                continue
            pair = (s, t)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            node_map[s] = s
            node_map[t] = t
            edges_out.append(GraphVisualizationEdge(id=f"e{ei}", source=s, target=t))
            ei += 1

    nodes = [GraphVisualizationNode(id=k, label=v) for k, v in sorted(node_map.items())]
    raw = GraphVisualizationData(nodes=nodes, edges=edges_out)
    return _clip_graph_by_node_cap(raw, max(1, node_cap))


def out_degree(driver: Driver, *, tenant_id: int) -> list[GraphDegreeItem]:
    tid = _require_tid(tenant_id)
    cypher = (
        "MATCH (a:User {tenant_id: $tid})-[:TRANSFER]->(b:User {tenant_id: $tid}) "
        "RETURN a.name AS name, count(*) AS degree "
        "ORDER BY degree DESC, name ASC"
    )
    with driver.session() as session:
        result = session.run(cypher, tid=tid)
        return [
            GraphDegreeItem(name=r["name"], degree=int(r["degree"]))
            for r in result
        ]
