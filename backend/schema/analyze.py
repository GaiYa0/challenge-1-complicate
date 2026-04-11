from pydantic import BaseModel, field_serializer


def _serialize_score(v: float) -> float | int:
    """30.0 → 30, 72.3 → 72.3（与原有行为一致）。"""
    return int(v) if v == int(v) else round(v, 1)


class AnalyzeMockData(BaseModel):
    score: float
    level: str

    _ser_score = field_serializer("score")(_serialize_score)


class AnalyzeIforestData(BaseModel):
    """字段顺序与原始 API 一致：total, anomaly, score, level。"""

    total: int
    anomaly: int
    score: float
    level: str

    _ser_score = field_serializer("score")(_serialize_score)


class AnalyzeGraphUserItem(BaseModel):
    name: str
    risk: int


class AnalyzeGraphData(BaseModel):
    """字段顺序与原始 API 一致：users, score, level。"""

    users: list[AnalyzeGraphUserItem]
    score: float
    level: str

    _ser_score = field_serializer("score")(_serialize_score)
