"""
资金流异常分析引擎：高频小额、统计大额异常、有向图资金环路（NetworkX）。

输入 DataFrame 建议列：
- from_account: 转出方（person）
- to_account: 转入方 / 对手
- amount: 金额（float）
- txn_time: 交易时间（datetime 或可解析）

输出：
{
  "anomalies": [ ... ],
  "graph_data": { "nodes": [...], "edges": [...] }
}
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from networkx import DiGraph
from networkx.algorithms.cycles import simple_cycles

# ---------------------------------------------------------------------------
# 图数据（供前端 G6 / 可视化）
# ---------------------------------------------------------------------------


def build_graph_data(df: pd.DataFrame) -> dict[str, Any]:
    """聚合边：按 (from_account, to_account) 汇总笔数与金额。"""
    if df.empty or not {"from_account", "to_account"}.issubset(df.columns):
        return {"nodes": [], "edges": []}

    agg = (
        df.groupby(["from_account", "to_account"], as_index=False)
        .agg(txn_count=("amount", "count"), total_amount=("amount", "sum"))
    )
    nodes_set: set[str] = set()
    for _, r in agg.iterrows():
        nodes_set.add(str(r["from_account"]))
        nodes_set.add(str(r["to_account"]))

    nodes = [{"id": n, "label": n} for n in sorted(nodes_set)]
    edges = [
        {
            "source": str(r["from_account"]),
            "target": str(r["to_account"]),
            "txn_count": int(r["txn_count"]),
            "total_amount": float(round(r["total_amount"], 2)),
        }
        for _, r in agg.iterrows()
    ]
    return {"nodes": nodes, "edges": edges}


# ---------------------------------------------------------------------------
# 一、高频小额（按 person=from_account，同一对手，滑动时间窗内笔数）
# ---------------------------------------------------------------------------


def _high_freq_small_for_pair(
    g: pd.DataFrame,
    *,
    small_threshold: float,
    min_count: int,
    window: str,
) -> tuple[float, int] | None:
    """
    仅保留 amount < small_threshold 的记录；在 txn_time 上 rolling 计数。
    返回 (score, max_count) 若 max_count >= min_count，否则 None。
    """
    if g.empty or len(g) < min_count:
        return None
    g = g.sort_values("txn_time")
    idx = pd.DatetimeIndex(pd.to_datetime(g["txn_time"], errors="coerce", format="mixed"))
    if idx.isna().all():
        return None
    g = g.assign(_ts=idx).dropna(subset=["_ts"])
    if g.empty:
        return None
    g = g[g["amount"] < small_threshold]
    if len(g) < min_count:
        return None

    g = g.set_index("_ts").sort_index()
    g["_one"] = 1.0
    roll = g["_one"].rolling(window, min_periods=1).sum()
    max_cnt = int(roll.max()) if len(roll) else 0
    if max_cnt < min_count:
        return None
    # 分数：随超出阈值笔数上升，封顶 100
    score = min(100.0, 40.0 + (max_cnt - min_count + 1) * 8.0)
    return score, max_cnt


def detect_high_freq_small(
    df: pd.DataFrame,
    *,
    small_amount_threshold: float = 50_000.0,
    min_count: int = 5,
    windows: tuple[str, str] = ("1h", "24h"),
) -> list[dict[str, Any]]:
    """
    按 (from_account, to_account) 分组，在 1h / 24h 窗口内统计「小额」交易笔数。
    规则：单笔金额 < small_amount_threshold 且窗口内笔数 >= min_count。
    """
    need = {"from_account", "to_account", "amount", "txn_time"}
    if not need.issubset(df.columns):
        raise ValueError(f"缺少列: {need - set(df.columns)}")

    out: list[dict[str, Any]] = []
    for (fa, ta), sub in df.groupby(["from_account", "to_account"], sort=False):
        for win in windows:
            res = _high_freq_small_for_pair(
                sub,
                small_threshold=small_amount_threshold,
                min_count=min_count,
                window=win,
            )
            if res is None:
                continue
            score, max_cnt = res
            out.append(
                {
                    "type": "high_freq_small",
                    "window": win,
                    "score": round(score, 2),
                    "related_accounts": [str(fa), str(ta)],
                    "from_account": str(fa),
                    "to_account": str(ta),
                    "max_count_in_window": max_cnt,
                    "small_amount_threshold": small_amount_threshold,
                }
            )
    return out


# ---------------------------------------------------------------------------
# 二、大额异常：amount > mean + z_multiplier * std（按 from_account）
# ---------------------------------------------------------------------------


def detect_large_amount_anomalies(
    df: pd.DataFrame,
    *,
    z_multiplier: float = 3.0,
    min_group_size: int = 3,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if "from_account" not in df.columns or "amount" not in df.columns:
        return out

    for fa, g in df.groupby("from_account", sort=False):
        if len(g) < min_group_size:
            continue
        amt = pd.to_numeric(g["amount"], errors="coerce")
        if amt.notna().sum() < min_group_size:
            continue
        mu = float(amt.mean())
        sigma = float(amt.std(ddof=0))
        if sigma == 0 or np.isnan(sigma):
            continue
        thresh = mu + z_multiplier * sigma
        for idx, row in g.iterrows():
            a = row["amount"]
            try:
                av = float(a)
            except (TypeError, ValueError):
                continue
            if av > thresh:
                # 分数：相对阈值的超出程度，封顶 100
                excess = (av - thresh) / max(thresh, 1e-9)
                score = min(100.0, 50.0 + min(50.0, excess * 20.0))
                out.append(
                    {
                        "type": "large_amount",
                        "score": round(score, 2),
                        "from_account": str(fa),
                        "to_account": str(row.get("to_account", "")),
                        "amount": round(av, 2),
                        "mean": round(mu, 2),
                        "std": round(sigma, 2),
                        "threshold": round(thresh, 2),
                        "z_multiplier": z_multiplier,
                        "txn_time": row.get("txn_time"),
                        "row_index": idx,
                    }
                )
    return out


# ---------------------------------------------------------------------------
# 三、资金环路：有向图 simple_cycles，长度 3~6
# ---------------------------------------------------------------------------


def detect_fund_cycles(
    df: pd.DataFrame,
    *,
    min_len: int = 3,
    max_len: int = 6,
    max_cycles: int = 5000,
) -> list[dict[str, Any]]:
    """
    构建 DiGraph(from_account -> to_account)，枚举简单有向环，筛选长度 [min_len, max_len]。
    """
    if df.empty or not {"from_account", "to_account"}.issubset(df.columns):
        return []

    G = DiGraph()
    for _, r in df.iterrows():
        u, v = str(r["from_account"]), str(r["to_account"])
        if u == v:
            continue
        if not G.has_edge(u, v):
            G.add_edge(u, v)
        # 多重边合并为单边即可；环路检测不依赖权重

    found: list[dict[str, Any]] = []
    n_found = 0
    for cyc in simple_cycles(G):
        ln = len(cyc)
        if min_len <= ln <= max_len:
            # 环路洗钱特征：略高基础分 + 长度惩罚
            score = min(100.0, 60.0 + ln * 6.0)
            found.append(
                {
                    "type": "fund_cycle",
                    "score": round(score, 2),
                    "cycle": [str(x) for x in cyc],
                    "length": ln,
                    "related_accounts": [str(x) for x in sorted(set(cyc))],
                }
            )
            n_found += 1
            if n_found >= max_cycles:
                break
    return found


# ---------------------------------------------------------------------------
# 总入口
# ---------------------------------------------------------------------------


def analyze_fund_flow(
    df: pd.DataFrame,
    *,
    small_amount_threshold: float = 50_000.0,
    high_freq_min_count: int = 5,
    high_freq_windows: tuple[str, str] = ("1h", "24h"),
    large_z_multiplier: float = 3.0,
    cycle_min_len: int = 3,
    cycle_max_len: int = 6,
    max_cycles: int = 5000,
) -> dict[str, Any]:
    """
    汇总：高频小额 + 大额统计异常 + 资金环路 + graph_data。
    """
    if df is None:
        df = pd.DataFrame()
    df = df.copy()
    if not df.empty and "txn_time" in df.columns:
        df["txn_time"] = pd.to_datetime(df["txn_time"], errors="coerce", format="mixed")

    anomalies: list[dict[str, Any]] = []
    anomalies.extend(
        detect_high_freq_small(
            df,
            small_amount_threshold=small_amount_threshold,
            min_count=high_freq_min_count,
            windows=high_freq_windows,
        )
    )
    anomalies.extend(
        detect_large_amount_anomalies(df, z_multiplier=large_z_multiplier)
    )
    anomalies.extend(
        detect_fund_cycles(
            df,
            min_len=cycle_min_len,
            max_len=cycle_max_len,
            max_cycles=max_cycles,
        )
    )

    graph_data = build_graph_data(df)
    return {"anomalies": anomalies, "graph_data": graph_data}


# ---------------------------------------------------------------------------
# 示例
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    demo = pd.DataFrame(
        [
            # A -> B 高频小额（1 小时内多笔）
            *[
                ("A", "B", 1000.0 + i * 10, f"2024-01-01 10:{i:02d}:00")
                for i in range(6)
            ],
            # A -> C 大额相对自身分布异常
            ("A", "C", 500.0, "2024-01-02 09:00:00"),
            ("A", "C", 600.0, "2024-01-02 10:00:00"),
            ("A", "C", 550.0, "2024-01-02 11:00:00"),
            ("A", "C", 99_999.0, "2024-01-02 12:00:00"),
            # 环路 A -> B -> C -> A
            ("B", "C", 10_000.0, "2024-01-03 08:00:00"),
            ("C", "A", 10_000.0, "2024-01-03 09:00:00"),
            ("A", "B", 5_000.0, "2024-01-03 10:00:00"),
        ],
        columns=["from_account", "to_account", "amount", "txn_time"],
    )

    result = analyze_fund_flow(demo)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
