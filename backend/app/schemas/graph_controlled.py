from __future__ import annotations

from typing import Any

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


class MergedGraphNode(BaseModel):
    id: str
    label: str
    type: str = "person"
    degree: int | None = None
    centrality: float | None = None
    case_ids: list[int] = []


class MergedGraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str = "TRANSFER"
    weight: float = 1.0
    case_id: int | None = None


class MergedGraphData(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    case_ids: list[int] = []
