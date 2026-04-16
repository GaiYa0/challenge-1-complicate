from __future__ import annotations

from pydantic import BaseModel, Field


class ControlledGraphNode(BaseModel):
    id: str
    label: str
    type: str = Field(description="person | account | location")
    degree: int | None = None
    centrality: float | None = None


class ControlledGraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str = "TRANSFER"
    weight: float = 1.0


class ControlledGraphData(BaseModel):
    nodes: list[ControlledGraphNode]
    edges: list[ControlledGraphEdge]
