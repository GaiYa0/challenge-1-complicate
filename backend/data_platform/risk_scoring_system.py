"""
风险评分系统：四维加权求最终 Risk Score（0~100）与等级（high / medium / low）。

公式：
  Risk = w1 * fund + w2 * call + w3 * trip + w4 * graph

权重可配置；若之和不为 1，将按比例归一化（全为 0 时退化为均等权重）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

# 与 multi_source_collision_engine 中 person_features 键名一致
DEFAULT_WEIGHTS: dict[str, float] = {
    "fund": 0.25,
    "call": 0.25,
    "trip": 0.25,
    "graph": 0.25,
}


@dataclass(frozen=True)
class RiskLevelThresholds:
    """score >= high_min → high；>= medium_min → medium；否则 low。"""

    high_min: float = 70.0
    medium_min: float = 40.0

    def __post_init__(self) -> None:
        if self.medium_min > self.high_min:
            raise ValueError("medium_min 不能大于 high_min")
        if self.high_min > 100 or self.medium_min < 0:
            raise ValueError("阈值须在 0~100 内")


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def normalize_weights(
    weights: Mapping[str, float] | Sequence[float] | None,
) -> tuple[float, float, float, float]:
    """
    返回 (w_fund, w_call, w_trip, w_graph)。

    支持：
    - dict：键 fund / call / trip / graph（缺省视为 0）
    - 序列 (w1, w2, w3, w4) 顺序对应 fund, call, trip, graph
    - None：使用 DEFAULT_WEIGHTS
    """
    if weights is None:
        w = DEFAULT_WEIGHTS
        return (
            float(w["fund"]),
            float(w["call"]),
            float(w["trip"]),
            float(w["graph"]),
        )

    if isinstance(weights, Mapping):
        wf = float(weights.get("fund", 0) or 0)
        wc = float(weights.get("call", 0) or 0)
        wt = float(weights.get("trip", 0) or 0)
        wg = float(weights.get("graph", 0) or 0)
    else:
        seq = list(weights)
        if len(seq) != 4:
            raise ValueError("序列权重须为 4 项：(fund, call, trip, graph)")
        wf, wc, wt, wg = (float(x) for x in seq)

    s = wf + wc + wt + wg
    if s <= 0:
        return 0.25, 0.25, 0.25, 0.25
    return wf / s, wc / s, wt / s, wg / s


def weighted_risk_score(
    fund: float,
    call: float,
    trip: float,
    graph: float,
    weights: Mapping[str, float] | Sequence[float] | None = None,
) -> float:
    """
    Risk = w1*fund + w2*call + w3*trip + w4*graph，结果限制在 [0, 100]。

    各分量假定已在 0~100（与统一特征向量一致）。
    """
    f = _clamp(float(fund))
    c = _clamp(float(call))
    t = _clamp(float(trip))
    g = _clamp(float(graph))
    wf, wc, wt, wg = normalize_weights(weights)
    raw = wf * f + wc * c + wt * t + wg * g
    return round(_clamp(raw), 2)


def classify_risk_level(
    risk_score: float,
    *,
    thresholds: RiskLevelThresholds | None = None,
) -> str:
    """返回 high / medium / low。"""
    th = thresholds or RiskLevelThresholds()
    s = float(risk_score)
    if s >= th.high_min:
        return "high"
    if s >= th.medium_min:
        return "medium"
    return "low"


def assess_risk(
    fund: float,
    call: float,
    trip: float,
    graph: float,
    *,
    weights: Mapping[str, float] | Sequence[float] | None = None,
    level_thresholds: RiskLevelThresholds | None = None,
) -> dict[str, Any]:
    """
    输出：
    {
      "risk_score": float,  # 0~100
      "level": "high" | "medium" | "low",
    }
    """
    score = weighted_risk_score(fund, call, trip, graph, weights=weights)
    level = classify_risk_level(score, thresholds=level_thresholds)
    return {"risk_score": score, "level": level}


def assess_risk_from_features(
    features: Mapping[str, float],
    *,
    weights: Mapping[str, float] | Sequence[float] | None = None,
    level_thresholds: RiskLevelThresholds | None = None,
) -> dict[str, Any]:
    """从 person_features 单条记录计算，键：fund_score, call_score, trip_score, graph_score。"""
    fund = float(features.get("fund_score", 0) or 0)
    call = float(features.get("call_score", 0) or 0)
    trip = float(features.get("trip_score", 0) or 0)
    graph = float(features.get("graph_score", 0) or 0)
    return assess_risk(
        fund,
        call,
        trip,
        graph,
        weights=weights,
        level_thresholds=level_thresholds,
    )


if __name__ == "__main__":
    import json

    demo = assess_risk(80, 60, 40, 20, weights={"fund": 0.4, "call": 0.3, "trip": 0.2, "graph": 0.1})
    print(json.dumps(demo, ensure_ascii=False, indent=2))

    demo2 = assess_risk_from_features(
        {"fund_score": 50, "call_score": 50, "trip_score": 50, "graph_score": 50},
        weights=(0.25, 0.25, 0.25, 0.25),
    )
    print(json.dumps(demo2, ensure_ascii=False, indent=2))
