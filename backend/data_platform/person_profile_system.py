"""
人物画像系统：四维画像（经济 / 轨迹 / 社会关系 / 异常）+ 风险分 + 可解释标签与模板摘要。

依赖 multi_source_collision_engine.build_person_features 与 risk_scoring_system.assess_risk。

输出（顶层字段）：
{
  "basic_info": { ..., "risk_level": "high"|"medium"|"low" },
  "risk_score": float,
  "tags": [ { "tag", "reason" }, ... ],
  "summary": str,
  "charts": { ... },
}
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .multi_source_collision_engine import build_person_features
from .risk_scoring_system import RiskLevelThresholds, assess_risk, normalize_weights


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _social_score(call_s: float, graph_s: float) -> float:
    return round(_clamp((float(call_s) + float(graph_s)) / 2.0), 2)


def _anomaly_dimension_score(
    person_id: str,
    fund_result: dict[str, Any] | None,
    call_result: dict[str, Any] | None,
    trajectory_result: dict[str, Any] | None,
    collision_events: list[dict[str, Any]] | None,
) -> tuple[float, list[str]]:
    """
    异常行为维度分（0~100）及可解释信号列表。
    综合：资金异常条数、夜间通话占比、轨迹可疑/伴随、碰撞事件。
    """
    pid = str(person_id)
    signals: list[str] = []
    parts: list[float] = []

    # 资金异常（涉该人）
    n_fund = 0
    sum_sev = 0.0
    if fund_result:
        for a in fund_result.get("anomalies") or []:
            fa = str(a.get("from_account", "") or "")
            ta = str(a.get("to_account", "") or "")
            if pid not in (fa, ta):
                continue
            n_fund += 1
            sum_sev += float(a.get("score", 0) or 0)
    if n_fund:
        parts.append(min(100.0, n_fund * 18.0 + sum_sev * 0.08))
        signals.append(
            f"资金侧命中 {n_fund} 条异常记录（累计异常强度约 {sum_sev:.1f}）。"
        )

    # 通话：夜间占比（全局指标，解释中注明）
    night = float((call_result or {}).get("night_call_ratio") or 0)
    if night > 0.2:
        parts.append(min(100.0, 30.0 + night * 50.0))
        signals.append(
            f"通话数据中夜间时段（22:00–06:00）占比 {night:.0%}，高于常见关注阈值 20%。"
        )
    elif night > 0:
        signals.append(
            f"夜间通话占比 {night:.0%}，未超过 20% 关注阈值。"
        )

    # 轨迹
    n_trip = 0
    n_co = 0
    if trajectory_result:
        for t in trajectory_result.get("suspicious_trips") or []:
            if str(t.get("person_id")) == pid:
                n_trip += 1
        for c in trajectory_result.get("co_occurrence") or []:
            if str(c.get("person_a")) == pid or str(c.get("person_b")) == pid:
                n_co += 1
    if n_trip:
        parts.append(min(100.0, 20.0 + n_trip * 25.0))
        signals.append(f"轨迹侧存在 {n_trip} 次敏感区域短停折返类记录。")
    if n_co:
        parts.append(min(100.0, 15.0 + n_co * 12.0))
        signals.append(f"与其他对象存在 {n_co} 条时空伴随记录。")

    # 多源碰撞事件
    ev_score = 0.0
    n_ev = 0
    for ev in collision_events or []:
        if ev.get("type") == "rule_error":
            continue
        pa, pb = str(ev.get("person_a", "")), str(ev.get("person_b", ""))
        ponly = str(ev.get("person_id", ""))
        hit = pid in (pa, pb) or pid == ponly
        if not hit:
            continue
        n_ev += 1
        ev_score = max(ev_score, float(ev.get("score") or 0))
    if n_ev:
        parts.append(ev_score)
        signals.append(
            f"多源碰撞规则命中 {n_ev} 次，最高事件分 {ev_score:.1f}。"
        )

    if not parts:
        score = 0.0
        signals.append("当前数据源中未检出显著异常行为信号。")
    else:
        score = round(_clamp(max(parts)), 2)

    return score, signals


def _economic_signals(
    person_id: str, fund_result: dict[str, Any] | None, fund_score: float
) -> list[str]:
    pid = str(person_id)
    lines: list[str] = []
    if not fund_result:
        lines.append("暂无资金流水分析结果，经济状况维度依据不足。")
        return lines
    rows = [
        a
        for a in fund_result.get("anomalies") or []
        if str(a.get("from_account", "") or "") == pid
        or str(a.get("to_account", "") or "") == pid
    ]
    if not rows:
        lines.append("资金侧未列出与该对象直接相关的异常项。")
    for a in rows[:5]:
        lines.append(
            f"类型「{a.get('type', 'unknown')}」，"
            f"异常分约 {float(a.get('score', 0) or 0):.1f}。"
        )
    lines.append(f"经济状况综合分（0–100）为 {fund_score:.1f}，由资金异常引擎加权汇总。")
    return lines


def _behavior_signals(
    person_id: str, trajectory_result: dict[str, Any] | None, trip_score: float
) -> list[str]:
    pid = str(person_id)
    lines: list[str] = []
    if not trajectory_result:
        lines.append("暂无轨迹数据，行为轨迹维度依据不足。")
        return lines
    st = [t for t in trajectory_result.get("suspicious_trips") or [] if str(t.get("person_id")) == pid]
    co = [
        c
        for c in trajectory_result.get("co_occurrence") or []
        if str(c.get("person_a")) == pid or str(c.get("person_b")) == pid
    ]
    lines.append(
        f"可疑出行片段 {len(st)} 次，涉及时空伴随 {len(co)} 条（与本人相关）。"
    )
    lines.append(f"行为轨迹综合分（0–100）为 {trip_score:.1f}，由轨迹异常引擎汇总。")
    return lines


def _social_signals(
    call_result: dict[str, Any] | None,
    call_score: float,
    graph_score: float,
) -> list[str]:
    lines: list[str] = []
    if not call_result:
        lines.append("暂无通话记录分析，社会关系维度依据不足。")
        return lines
    night = float(call_result.get("night_call_ratio") or 0)
    lines.append(f"全网夜间通话占比统计为 {night:.0%}（用于通话行为背景，非单人精确值时以全局为准）。")
    top = call_result.get("top_contacts") or []
    if top:
        lines.append(f"高频联系人 TOP 列表共 {len(top)} 条（见原始分析）。")
    lines.append(
        f"通话行为分 {call_score:.1f}，关系图结构分 {graph_score:.1f}；"
        f"社会关系维度取二者均值。"
    )
    return lines


def _build_tags(
    fund_score: float,
    trip_score: float,
    social_score: float,
    anomaly_score: float,
    level: str,
    collision_events: list[dict[str, Any]] | None,
    person_id: str,
) -> list[dict[str, str]]:
    pid = str(person_id)
    tags: list[dict[str, str]] = []

    def add(tag: str, reason: str) -> None:
        tags.append({"tag": tag, "reason": reason})

    if fund_score >= 70:
        add("经济状况-高关注", f"资金维度分 {fund_score:.0f}，达到高关注区间。")
    elif fund_score >= 40:
        add("经济状况-中关注", f"资金维度分 {fund_score:.0f}，建议结合流水复核。")

    if trip_score >= 70:
        add("轨迹-高关注", f"行为轨迹分 {trip_score:.0f}，存在较多轨迹异常信号。")
    elif trip_score >= 40:
        add("轨迹-中关注", f"行为轨迹分 {trip_score:.0f}。")

    if social_score >= 70:
        add("社交-高关注", f"社会关系维度分 {social_score:.0f}，通话/图结构突出。")
    elif social_score >= 40:
        add("社交-中关注", f"社会关系维度分 {social_score:.0f}。")

    if anomaly_score >= 70:
        add("异常行为-高关注", f"异常行为维度分 {anomaly_score:.0f}，多源异常叠加。")
    elif anomaly_score >= 40:
        add("异常行为-中关注", f"异常行为维度分 {anomaly_score:.0f}。")

    add(f"综合风险-{level}", f"加权风险分对应等级「{level}」。")

    for ev in collision_events or []:
        if ev.get("type") == "rule_error":
            continue
        if str(ev.get("person_a")) == pid or str(ev.get("person_b")) == pid or str(ev.get("person_id")) == pid:
            rid = str(ev.get("rule_id", ""))
            if rid and not any(t["tag"] == f"碰撞-{rid}" for t in tags):
                add(
                    f"碰撞-{rid}",
                    f"规则 {rid} 命中，事件分约 {float(ev.get('score', 0) or 0):.1f}。",
                )

    return tags


def _build_summary(
    person_id: str,
    name: str | None,
    risk_score: float,
    level: str,
    economic: float,
    behavior: float,
    social: float,
    anomaly: float,
) -> str:
    display = name or person_id
    return (
        f"【对象】{display}（ID: {person_id}）\n"
        f"【综合风险】评分 {risk_score:.1f}，等级「{level}」"
        f"（高≥70 / 中≥40 / 低<40，阈值可配置）。\n"
        f"【经济状况】维度分 {economic:.1f}，反映资金异常引擎对该对象的资金侧刻画。\n"
        f"【行为轨迹】维度分 {behavior:.1f}，反映出行轨迹异常（短停折返、伴随等）。\n"
        f"【社会关系】维度分 {social:.1f}，综合通话行为与关系图结构位置。\n"
        f"【异常行为】维度分 {anomaly:.1f}，汇总多源异常与碰撞事件强度。\n"
        "以上分数均在 0~100 区间，可与业务阈值对照使用。"
    )


def build_person_profile(
    person_id: str,
    *,
    fund_result: dict[str, Any] | None = None,
    call_result: dict[str, Any] | None = None,
    trajectory_result: dict[str, Any] | None = None,
    collision_events: list[dict[str, Any]] | None = None,
    basic_info: Mapping[str, Any] | None = None,
    risk_weights: Mapping[str, float] | Sequence[float] | None = None,
    level_thresholds: RiskLevelThresholds | None = None,
) -> dict[str, Any]:
    """
    生成单对象人物画像。

    collision_events：来自 run_multi_source_collision(..., include_person_features=False)["events"]。
    """
    pid = str(person_id)
    pf_map = build_person_features(
        fund_result,
        call_result,
        trajectory_result,
        extra_person_ids={pid},
    )
    feat = pf_map.get(pid, {
        "fund_score": 0.0,
        "call_score": 0.0,
        "trip_score": 0.0,
        "graph_score": 0.0,
    })

    fs = float(feat["fund_score"])
    cs = float(feat["call_score"])
    ts = float(feat["trip_score"])
    gs = float(feat["graph_score"])

    soc = _social_score(cs, gs)
    ano, ano_signals = _anomaly_dimension_score(
        pid, fund_result, call_result, trajectory_result, collision_events
    )

    risk = assess_risk(fs, cs, ts, gs, weights=risk_weights, level_thresholds=level_thresholds)
    risk_score = float(risk["risk_score"])
    level = str(risk["level"])
    wf, wc, wt, wg = normalize_weights(risk_weights)

    econ_sig = _economic_signals(pid, fund_result, fs)
    beh_sig = _behavior_signals(pid, trajectory_result, ts)
    soc_sig = _social_signals(call_result, cs, gs)

    tags = _build_tags(fs, ts, soc, ano, level, collision_events, pid)

    charts: dict[str, Any] = {
        "radar": {
            "labels": ["经济状况", "行为轨迹", "社会关系", "异常行为"],
            "values": [fs, ts, soc, ano],
            "keys": ["economic", "behavior", "social", "anomaly"],
        },
        "dimension_detail": {
            "economic": {
                "score": fs,
                "title": "经济状况",
                "explanation": "来源于资金流水异常引擎对「与该对象相关」异常记录的加权汇总。",
                "signals": econ_sig,
            },
            "behavior": {
                "score": ts,
                "title": "行为轨迹",
                "explanation": "来源于轨迹异常（敏感区短停折返、时空伴随等）强度。",
                "signals": beh_sig,
            },
            "social": {
                "score": soc,
                "title": "社会关系",
                "explanation": "取通话行为分与关系图结构分的算术平均，刻画通信与图位置。",
                "signals": soc_sig,
            },
            "anomaly": {
                "score": ano,
                "title": "异常行为",
                "explanation": "汇总资金/夜间通话/轨迹/多源碰撞等异常线索，取分项贡献的最大包络并封顶。",
                "signals": ano_signals,
            },
        },
        "risk_breakdown": {
            "fund_score": fs,
            "call_score": cs,
            "trip_score": ts,
            "graph_score": gs,
            "weights": {"fund": wf, "call": wc, "trip": wt, "graph": wg},
        },
    }

    bi: dict[str, Any] = {"person_id": pid}
    if basic_info:
        bi.update(dict(basic_info))
    name = bi.get("name")
    if isinstance(name, str):
        pass
    else:
        name = None

    summary = _build_summary(pid, name, risk_score, level, fs, ts, soc, ano)

    bi["risk_level"] = level

    return {
        "basic_info": bi,
        "risk_score": risk_score,
        "tags": tags,
        "summary": summary,
        "charts": charts,
    }


if __name__ == "__main__":
    import json

    demo = build_person_profile(
        "U1",
        fund_result={"anomalies": [{"type": "large_amount", "from_account": "U1", "to_account": "X", "score": 80}]},
        call_result={"night_call_ratio": 0.25, "top_contacts": [], "central_nodes": []},
        trajectory_result={"suspicious_trips": [], "co_occurrence": []},
        collision_events=[],
        basic_info={"name": "示例人员"},
    )
    print(json.dumps(demo, ensure_ascii=False, indent=2, default=str))
