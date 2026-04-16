"""
多源数据碰撞引擎：资金 / 通话 / 轨迹融合，统一特征向量 + 可扩展规则 + 风险分。

输出（默认含 person_features；可关）：
{
  "events": [],
  "risk_score": float,
  "person_features"?: { person_id: { fund_score, call_score, trip_score, graph_score } },
}

规则通过 CollisionRule 协议与 RuleRegistry 注册；默认包含「时空伴随 + 同期通话」等示例规则。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable

import pandas as pd

# ---------------------------------------------------------------------------
# 统一特征向量
# ---------------------------------------------------------------------------


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _extract_persons_from_fund(fund_result: dict[str, Any] | None) -> set[str]:
    s: set[str] = set()
    if not fund_result:
        return s
    for a in fund_result.get("anomalies") or []:
        for k in ("from_account", "to_account", "person_id"):
            v = a.get(k)
            if v is not None:
                s.add(str(v))
    return s


def _fund_score_for_person(person_id: str, fund_result: dict[str, Any] | None) -> float:
    if not fund_result:
        return 0.0
    pid = str(person_id)
    total = 0.0
    for a in fund_result.get("anomalies") or []:
        fa = str(a.get("from_account", "") or "")
        ta = str(a.get("to_account", "") or "")
        if pid not in (fa, ta):
            continue
        sc = float(a.get("score", 0) or 0)
        total += sc * 0.15
    return _clamp(total)


def _call_score_for_person(person_id: str, call_result: dict[str, Any] | None) -> float:
    if not call_result:
        return 0.0
    pid = str(person_id)
    night = float(call_result.get("night_call_ratio") or 0)
    base = night * 80.0
    for row in call_result.get("central_nodes") or []:
        if str(row.get("node")) == pid:
            bc = float(row.get("betweenness_centrality") or 0)
            pr = float(row.get("pagerank") or 0)
            base = max(base, bc * 60.0 + pr * 40.0)
            break
    return _clamp(base)


def _trip_score_for_person(person_id: str, trajectory_result: dict[str, Any] | None) -> float:
    if not trajectory_result:
        return 0.0
    pid = str(person_id)
    n = 0
    for t in trajectory_result.get("suspicious_trips") or []:
        if str(t.get("person_id")) == pid:
            n += 1
    m = 0
    for c in trajectory_result.get("co_occurrence") or []:
        if str(c.get("person_a")) == pid or str(c.get("person_b")) == pid:
            m += 1
    return _clamp(n * 22.0 + m * 12.0)


def _graph_score_for_person(person_id: str, call_result: dict[str, Any] | None) -> float:
    """通话关系图中心性（与 call_score 中图维度区分：此处强调结构位置）。"""
    if not call_result:
        return 0.0
    pid = str(person_id)
    for row in call_result.get("central_nodes") or []:
        if str(row.get("node")) == pid:
            dc = float(row.get("degree_centrality") or 0)
            bc = float(row.get("betweenness_centrality") or 0)
            return _clamp(dc * 45.0 + bc * 55.0)
    return 0.0


def build_person_features(
    fund_result: dict[str, Any] | None,
    call_result: dict[str, Any] | None,
    trajectory_result: dict[str, Any] | None,
    *,
    extra_person_ids: set[str] | None = None,
) -> dict[str, dict[str, float]]:
    """每人一条：fund_score, call_score, trip_score, graph_score（0–100）。"""
    persons: set[str] = set()
    persons |= _extract_persons_from_fund(fund_result)
    if call_result:
        for row in call_result.get("central_nodes") or []:
            persons.add(str(row.get("node", "")))
    if trajectory_result:
        for t in trajectory_result.get("suspicious_trips") or []:
            persons.add(str(t.get("person_id", "")))
        for c in trajectory_result.get("co_occurrence") or []:
            persons.add(str(c.get("person_a", "")))
            persons.add(str(c.get("person_b", "")))
    if extra_person_ids:
        persons |= {str(x) for x in extra_person_ids}
    persons.discard("")

    out: dict[str, dict[str, float]] = {}
    for p in sorted(persons):
        out[p] = {
            "fund_score": round(_fund_score_for_person(p, fund_result), 2),
            "call_score": round(_call_score_for_person(p, call_result), 2),
            "trip_score": round(_trip_score_for_person(p, trajectory_result), 2),
            "graph_score": round(_graph_score_for_person(p, call_result), 2),
        }
    return out


# ---------------------------------------------------------------------------
# 可扩展规则系统
# ---------------------------------------------------------------------------


@dataclass
class CollisionContext:
    """规则评估上下文。"""

    person_features: dict[str, dict[str, float]]
    fund_result: dict[str, Any] | None
    call_result: dict[str, Any] | None
    trajectory_result: dict[str, Any] | None
    call_df: pd.DataFrame | None = None
    trajectory_df: pd.DataFrame | None = None
    config: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class CollisionRule(Protocol):
    rule_id: str

    def evaluate(self, ctx: CollisionContext) -> list[dict[str, Any]]: ...


class RuleRegistry:
    """注册规则；后注册者可覆盖同 rule_id（按名称去重保留最后一个）。"""

    def __init__(self) -> None:
        self._rules: list[Callable[[CollisionContext], list[dict[str, Any]]]] = []
        self._ids: list[str] = []

    def register(
        self,
        rule_id: str,
        fn: Callable[[CollisionContext], list[dict[str, Any]]],
    ) -> None:
        self._rules.append(fn)
        self._ids.append(rule_id)

    def evaluate_all(self, ctx: CollisionContext) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for rid, fn in zip(self._ids, self._rules):
            try:
                batch = fn(ctx)
            except Exception as exc:  # noqa: BLE001 — 单条规则失败不拖垮整体
                events.append(
                    {
                        "rule_id": rid,
                        "type": "rule_error",
                        "severity": "low",
                        "score": 0.0,
                        "error": str(exc),
                    }
                )
                continue
            for ev in batch:
                if "rule_id" not in ev:
                    ev["rule_id"] = rid
                events.append(ev)
        return events


def _parse_ts(x: Any) -> pd.Timestamp | None:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    t = pd.to_datetime(x, errors="coerce", format="mixed")
    if pd.isna(t):
        return None
    return t


def rule_same_time_place_with_call(ctx: CollisionContext) -> list[dict[str, Any]]:
    """
    同时间 + 同地点（轨迹伴随） + 双人间存在通话 → 高风险碰撞。

    依赖：trajectory_result.co_occurrence；call_df 列 caller, callee, call_time。
    """
    cfg = ctx.config
    win_min = float(cfg.get("call_window_minutes", 30.0))

    trip = ctx.trajectory_result or {}
    co = trip.get("co_occurrence") or []
    cdf = ctx.call_df
    if not co or cdf is None or cdf.empty:
        return []
    need = {"caller", "callee", "call_time"}
    if not need.issubset(cdf.columns):
        return []

    cdf = cdf.copy()
    cdf["_ct"] = pd.to_datetime(cdf["call_time"], errors="coerce", format="mixed")
    cdf = cdf.dropna(subset=["_ct"])

    out: list[dict[str, Any]] = []
    for row in co:
        pa, pb = str(row.get("person_a", "")), str(row.get("person_b", ""))
        ta = _parse_ts(row.get("time_a"))
        tb = _parse_ts(row.get("time_b"))
        if not pa or not pb or ta is None or tb is None:
            continue
        t0 = min(ta, tb)
        t1 = max(ta, tb)
        low = t0 - pd.Timedelta(minutes=win_min)
        high = t1 + pd.Timedelta(minutes=win_min)

        mask = (
            (cdf["_ct"] >= low)
            & (cdf["_ct"] <= high)
            & (
                ((cdf["caller"].astype(str) == pa) & (cdf["callee"].astype(str) == pb))
                | ((cdf["caller"].astype(str) == pb) & (cdf["callee"].astype(str) == pa))
            )
        )
        hits = cdf.loc[mask]
        if hits.empty:
            continue

        dist = float(row.get("distance_m") or 0)
        score = _clamp(72.0 + min(28.0, (500.0 - min(dist, 500.0)) / 500.0 * 28.0))

        out.append(
            {
                "rule_id": "same_time_place_with_call",
                "type": "high_risk_collision",
                "severity": "high",
                "score": round(score, 2),
                "person_a": pa,
                "person_b": pb,
                "evidence": {
                    "co_occurrence": row,
                    "matching_calls": len(hits),
                    "call_window_minutes": win_min,
                },
            }
        )
    return out


def rule_fund_and_trip_same_person(ctx: CollisionContext) -> list[dict[str, Any]]:
    """同一人员在资金侧有异常分且轨迹侧有可疑出行 → 中高风险。"""
    fund = ctx.fund_result or {}
    trip = ctx.trajectory_result or {}
    events: list[dict[str, Any]] = []
    susp = {str(t.get("person_id")) for t in (trip.get("suspicious_trips") or [])}
    for pid in susp:
        if not pid:
            continue
        fs = _fund_score_for_person(pid, fund)
        if fs < 25.0:
            continue
        ts = _trip_score_for_person(pid, trip)
        if ts < 15.0:
            continue
        score = _clamp((fs + ts) / 2.0 * 1.1)
        events.append(
            {
                "rule_id": "fund_and_trip_same_person",
                "type": "multi_source_person",
                "severity": "medium",
                "score": round(score, 2),
                "person_id": pid,
                "evidence": {"fund_score": fs, "trip_score": ts},
            }
        )
    return events


def default_registry() -> RuleRegistry:
    reg = RuleRegistry()
    reg.register("same_time_place_with_call", rule_same_time_place_with_call)
    reg.register("fund_and_trip_same_person", rule_fund_and_trip_same_person)
    return reg


def compute_risk_score(
    events: list[dict[str, Any]],
    person_features: dict[str, dict[str, float]],
) -> float:
    """综合：有碰撞事件取事件分峰值，否则取人员四维最大值的均值峰值。"""
    scores: list[float] = []
    for ev in events:
        if ev.get("type") == "rule_error":
            continue
        s = ev.get("score")
        if isinstance(s, (int, float)):
            scores.append(float(s))
    if scores:
        return round(min(100.0, max(scores)), 2)

    if not person_features:
        return 0.0
    best = 0.0
    for vec in person_features.values():
        best = max(best, max(vec.values()) if vec else 0.0)
    return round(best, 2)


def run_multi_source_collision(
    fund_result: dict[str, Any] | None = None,
    call_result: dict[str, Any] | None = None,
    trajectory_result: dict[str, Any] | None = None,
    call_df: pd.DataFrame | None = None,
    trajectory_df: pd.DataFrame | None = None,
    *,
    registry: RuleRegistry | None = None,
    config: dict[str, Any] | None = None,
    extra_person_ids: set[str] | None = None,
    include_person_features: bool = True,
) -> dict[str, Any]:
    """
    主入口：构建统一特征、执行规则、输出 risk_score。

    registry 为 None 时使用 default_registry()；可通过 RuleRegistry.register 追加规则。
    include_person_features=False 时仅返回 { events, risk_score }（与对外契约一致）。
    """
    cfg = dict(config or {})
    pf = build_person_features(
        fund_result,
        call_result,
        trajectory_result,
        extra_person_ids=extra_person_ids,
    )
    ctx = CollisionContext(
        person_features=pf,
        fund_result=fund_result,
        call_result=call_result,
        trajectory_result=trajectory_result,
        call_df=call_df,
        trajectory_df=trajectory_df,
        config=cfg,
    )
    reg = registry if registry is not None else default_registry()
    events = reg.evaluate_all(ctx)
    risk = compute_risk_score(events, pf)
    out: dict[str, Any] = {
        "events": events,
        "risk_score": risk,
    }
    if include_person_features:
        out["person_features"] = pf
    return out


# ---------------------------------------------------------------------------
# 示例
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    fund_result = {
        "anomalies": [
            {"type": "large_amount", "from_account": "U1", "to_account": "X", "score": 70}
        ],
        "graph_data": {"nodes": [], "edges": []},
    }
    call_result = {
        "night_call_ratio": 0.1,
        "top_contacts": [],
        "central_nodes": [
            {"node": "U1", "degree_centrality": 0.3, "betweenness_centrality": 0.2, "pagerank": 0.1}
        ],
    }
    trajectory_result = {
        "suspicious_trips": [{"person_id": "U1", "stay_seconds": 60}],
        "co_occurrence": [
            {
                "person_a": "U1",
                "person_b": "U2",
                "time_a": "2024-07-01T10:00:00",
                "time_b": "2024-07-01T10:02:00",
                "distance_m": 100,
            }
        ],
    }
    call_df = pd.DataFrame(
        [
            ("U1", "U2", "2024-07-01 10:01:00"),
        ],
        columns=["caller", "callee", "call_time"],
    )

    r = run_multi_source_collision(
        fund_result=fund_result,
        call_result=call_result,
        trajectory_result=trajectory_result,
        call_df=call_df,
    )
    # 演示输出不含 person_features 冗余项
    out = {"events": r["events"], "risk_score": r["risk_score"]}
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    print("--- person_features ---")
    print(json.dumps(r["person_features"], ensure_ascii=False, indent=2))
