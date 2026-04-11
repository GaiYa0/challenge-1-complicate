"""
Service 层 —— 图谱业务逻辑
职责：封装 Neo4j 图操作的业务流程。
      ✅ 返回 Schema 对象
"""

from neo4j import Driver

from backend.core.exceptions import ServiceError
from backend.schema.graph import (
    GraphDegreeItem,
    GraphRelation,
    GraphVisualizationData,
    GraphVisualizationEdge,
    GraphVisualizationNode,
)


def create_user_node(driver: Driver, name: str, *, tenant_id: int | None = None) -> None:
    if tenant_id is not None:
        cypher = "MERGE (u:User {name: $name, tenant_id: $tid})"
        params = {"name": name, "tid": tenant_id}
    else:
        cypher = "MERGE (u:User {name: $name})"
        params = {"name": name}
    with driver.session() as session:
        session.run(cypher, **params)


def create_edge(driver: Driver, from_user: str, to_user: str) -> None:
    cypher = (
        "MATCH (a:User {name: $from_name}), (b:User {name: $to_name}) "
        "CREATE (a)-[:TRANSFER]->(b)"
    )
    with driver.session() as session:
        result = session.run(cypher, from_name=from_user, to_name=to_user)
        summary = result.consume()
        if summary.counters.relationships_created == 0:
            raise ServiceError("one or both users not found")


def list_relations(driver: Driver, *, tenant_id: int | None = None) -> list[GraphRelation]:
    if tenant_id is not None:
        cypher = (
            "MATCH (a:User {tenant_id: $tid})-[:TRANSFER]->(b:User) "
            "RETURN a.name AS from_name, b.name AS to_name"
        )
        params = {"tid": tenant_id}
    else:
        cypher = (
            "MATCH (a:User)-[:TRANSFER]->(b:User) "
            "RETURN a.name AS from_name, b.name AS to_name"
        )
        params = {}
    with driver.session() as session:
        result = session.run(cypher, **params)
        return [
            GraphRelation(from_user=r["from_name"], to_user=r["to_name"])
            for r in result
        ]


def build_visualization_data(
    driver: Driver,
    *,
    edge_limit: int = 500,
    tenant_id: int | None = None,
) -> GraphVisualizationData:
    """
    读取 User-[:TRANSFER]->User 边，组装为前端 G6 可用的 nodes/edges。
    边数上限避免一次拉全图拖垮浏览器；去重 (source, target) 重复边。
    """
    lim = max(1, min(edge_limit, 5000))
    if tenant_id is not None:
        cypher = (
            "MATCH (a:User {tenant_id: $tid})-[r:TRANSFER]->(b:User) "
            "RETURN a.name AS s, b.name AS t "
            "LIMIT $lim"
        )
        params: dict = {"tid": tenant_id, "lim": lim}
    else:
        cypher = (
            "MATCH (a:User)-[:TRANSFER]->(b:User) "
            "RETURN a.name AS s, b.name AS t "
            "LIMIT $lim"
        )
        params = {"lim": lim}

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
    return GraphVisualizationData(nodes=nodes, edges=edges_out)


def out_degree(driver: Driver, *, tenant_id: int | None = None) -> list[GraphDegreeItem]:
    if tenant_id is not None:
        cypher = (
            "MATCH (a:User {tenant_id: $tid})-[:TRANSFER]->() "
            "RETURN a.name AS name, count(*) AS degree"
        )
        params = {"tid": tenant_id}
    else:
        cypher = (
            "MATCH (a:User)-[:TRANSFER]->() "
            "RETURN a.name AS name, count(*) AS degree"
        )
        params = {}
    with driver.session() as session:
        result = session.run(cypher, **params)
        return [
            GraphDegreeItem(name=r["name"], degree=int(r["degree"]))
            for r in result
        ]
