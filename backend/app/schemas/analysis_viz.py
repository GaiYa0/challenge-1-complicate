"""多维可视化 API 契约：资金时间线+流向图、轨迹热力。"""

from typing import Any

from pydantic import BaseModel, Field


class FundTimelineEvent(BaseModel):
    ts: str = Field(description="ISO8601 时间")
    kind: str = Field(description="fund | call | anomaly")
    label: str = ""
    amount: float | None = None
    from_party: str | None = None
    to_party: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class FundGraphNode(BaseModel):
    id: str
    name: str
    category: str = "account"


class FundGraphEdge(BaseModel):
    source: str
    target: str
    value: float = Field(description="金额，用于边宽")
    label: str = ""


class FundVizData(BaseModel):
    """GET /analysis/fund"""

    fund_events: list[FundTimelineEvent]
    call_events: list[FundTimelineEvent]
    anomaly_events: list[FundTimelineEvent]
    graph_nodes: list[FundGraphNode]
    graph_edges: list[FundGraphEdge]


class TripPoint(BaseModel):
    person_id: str
    lat: float
    lng: float
    ts: str
    weight: float = 1.0


class TripCoOccurrence(BaseModel):
    person_a: str
    person_b: str
    lat: float
    lng: float
    ts: str
    distance_m: float | None = None


class HeatmapCell(BaseModel):
    lng: float
    lat: float
    value: float = Field(description="聚合强度")


class TripBounds(BaseModel):
    min_lng: float
    max_lng: float
    min_lat: float
    max_lat: float


class TripVizData(BaseModel):
    """GET /analysis/trip"""

    points: list[TripPoint]
    co_occurrence: list[TripCoOccurrence]
    heatmap_cells: list[HeatmapCell]
    bounds: TripBounds
