"""人物画像聚合 API 契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.app.schemas.graph import GraphVisualizationData


class PortraitBasicInfo(BaseModel):
    case_id: int
    person_id: str
    display_name: str = ""
    risk_score: float = Field(0, ge=0, le=100)
    risk_level: str = "low"
    summary: str = ""


class PortraitEconomic(BaseModel):
    """经济状况"""

    total_amount: float = Field(description="估算总交易额（元）")
    anomaly_ratio: float = Field(ge=0, le=1, description="异常线索占比（0~1）")
    transfer_out_count: int = 0
    transfer_in_count: int = 0
    explain: str = ""


class TimelineBin(BaseModel):
    hour: int = Field(ge=0, le=23)
    count: int = 0


class MapPoint(BaseModel):
    lat: float
    lng: float
    ts: str
    label: str = ""


class PortraitBehavior(BaseModel):
    """行为轨迹"""

    timeline_bins: list[TimelineBin]
    map_points: list[MapPoint]
    bounds: dict[str, float] = Field(
        default_factory=dict,
        description="min_lng,max_lng,min_lat,max_lat",
    )
    explain: str = ""


class PortraitSocial(BaseModel):
    """社会关系子图（有向资金）"""

    graph: GraphVisualizationData
    center_id: str
    explain: str = ""


class PortraitClueItem(BaseModel):
    id: int
    title: str
    risk_level: str
    risk_score: float = Field(ge=0, le=100)
    category: str = "general"


class PersonPortraitOut(BaseModel):
    """GET /cases/{case_id}/persons/{person_id}/portrait"""

    basic_info: PortraitBasicInfo
    economic: PortraitEconomic
    behavior: PortraitBehavior
    social: PortraitSocial
    clues: list[PortraitClueItem]
    links: dict[str, str] = Field(
        default_factory=dict,
        description="前端路由提示：如 clue_detail_pattern、network_path",
    )
