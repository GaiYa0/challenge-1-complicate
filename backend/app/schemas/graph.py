from pydantic import BaseModel, model_serializer


class GraphUserNodeIn(BaseModel):
    name: str


class GraphEdgeIn(BaseModel):
    from_user: str
    to_user: str
    amount: float | None = None


class GraphRelation(BaseModel):
    """序列化后 key 为 from / to（兼容原始 API）。"""

    from_user: str
    to_user: str

    @model_serializer
    def _serialize(self) -> dict[str, str]:
        return {"from": self.from_user, "to": self.to_user}


class GraphDegreeItem(BaseModel):
    name: str
    degree: int


class GraphVisualizationNode(BaseModel):
    """供 G6 等前端图引擎使用的节点（id 与边的 source/target 一致）。"""

    id: str
    label: str


class GraphVisualizationEdge(BaseModel):
    id: str
    source: str
    target: str
    weight: float | None = None


class GraphVisualizationData(BaseModel):
    """Neo4j User-[:TRANSFER]->User 子图，用于分析页可视化。"""

    nodes: list[GraphVisualizationNode]
    edges: list[GraphVisualizationEdge]
