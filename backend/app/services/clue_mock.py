"""
Mock 线索生成：在尚无 PG 线索时写入占位数据；默认多类随机，纯财付通案件可仅资金类。
"""

from __future__ import annotations

import random
from typing import Any

from backend.model.clue import Clue
from backend.model.clue_enums import ClueCategory, ClueRiskLevel


def _pick_risk_level() -> ClueRiskLevel:
    r = random.random()
    if r < 0.2:
        return ClueRiskLevel.high
    if r < 0.6:
        return ClueRiskLevel.medium
    return ClueRiskLevel.low


def _score_for_level(level: ClueRiskLevel) -> float:
    if level == ClueRiskLevel.high:
        return round(random.uniform(70.0, 100.0), 1)
    if level == ClueRiskLevel.medium:
        return round(random.uniform(40.0, 69.9), 1)
    return round(random.uniform(0.0, 39.9), 1)


def _rule_hits_for_category(cat: ClueCategory) -> list[str]:
    if cat == ClueCategory.fund:
        pool = [["高频小额交易", "异常账户集中"], ["大额异常转出", "资金归集可疑"], ["对手方集中度异常"]]
    elif cat == ClueCategory.call:
        pool = [["深夜通话", "高频联系人"], ["短时密集呼叫", "非工作时段异常"], ["通话对象与职务关联弱"]]
    elif cat == ClueCategory.trip:
        pool = [["敏感区域停留", "异常折返"], ["跨区域频繁活动", "轨迹与公务不符"], ["时空伴随可疑"]]
    else:
        pool = [["多源信息不一致", "需人工复核"], ["关联主体异常"], ["行为模式偏离基线"]]
    return random.choice(pool)


def _feature_snapshot(cat: ClueCategory, person_id: str) -> dict[str, Any]:
    base = {"person_id": person_id}
    if cat == ClueCategory.fund:
        base.update(
            {
                "transfer_out_30d_wan": round(random.uniform(10, 500), 1),
                "related_accounts": random.randint(2, 12),
            }
        )
    elif cat == ClueCategory.call:
        base.update(
            {
                "night_call_ratio": round(random.uniform(0.05, 0.45), 2),
                "distinct_peers_30d": random.randint(5, 40),
            }
        )
    elif cat == ClueCategory.trip:
        base.update(
            {
                "sensitive_visits_90d": random.randint(0, 8),
                "cross_city_trips": random.randint(1, 20),
            }
        )
    else:
        base.update({"flags": random.randint(0, 3)})
    return base


def _risk_prompts(level: ClueRiskLevel) -> list[dict[str, str]]:
    if level == ClueRiskLevel.high:
        return [{"level": "high", "text": "建议优先核查并固定电子数据"}]
    if level == ClueRiskLevel.medium:
        return [{"level": "medium", "text": "建议结合其他线索交叉验证"}]
    return [{"level": "low", "text": "可作为辅助参考"}]


def _title_and_summary(cat: ClueCategory, person_id: str, idx: int) -> tuple[str, str]:
    titles = {
        ClueCategory.fund: f"资金异常线索 #{idx}（{person_id}）",
        ClueCategory.call: f"通信行为线索 #{idx}（{person_id}）",
        ClueCategory.trip: f"轨迹异常线索 #{idx}（{person_id}）",
        ClueCategory.other: f"综合研判线索 #{idx}（{person_id}）",
    }
    summaries = {
        ClueCategory.fund: "基于流水统计与对手方分析生成的模拟摘要。",
        ClueCategory.call: "基于通话时段与频次统计生成的模拟摘要。",
        ClueCategory.trip: "基于轨迹停留与折返模式生成的模拟摘要。",
        ClueCategory.other: "基于多源特征融合生成的模拟摘要。",
    }
    return titles[cat], summaries[cat]


def generate_mock_clues(
    *,
    case_id: int,
    person_id: str,
    n: int | None = None,
    fund_only: bool = False,
) -> list[Clue]:
    """
    n: 线索条数；未指定时在 5~15 间随机。fund_only=True 时全部为资金类（纯财付通案件用）。
    """
    if n is not None:
        count = min(15, max(5, int(n)))
    else:
        count = random.randint(5, 15)
    cats = list(ClueCategory)
    rows: list[Clue] = []
    for i in range(count):
        cat = ClueCategory.fund if fund_only else random.choice(cats)
        level = _pick_risk_level()
        score = _score_for_level(level)
        title, summary = _title_and_summary(cat, person_id, i + 1)
        rh = _rule_hits_for_category(cat)
        rows.append(
            Clue(
                case_id=case_id,
                person_id=person_id,
                title=title,
                summary=summary,
                category=cat,
                risk_level=level,
                risk_score=score,
                rule_hits=rh,
                feature_snapshot=_feature_snapshot(cat, person_id),
                risk_prompts=_risk_prompts(level),
            )
        )
    return rows
