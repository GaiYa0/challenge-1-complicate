"""
通话记录分析引擎：深夜通话占比、高频联系人 TOP N、NetworkX 中心性（关键中间人）。

输入 DataFrame 建议列：
- caller: 主叫号码
- callee: 被叫号码
- call_time: 通话时间（datetime 或可解析）

输出：
{
  "night_call_ratio": float,
  "top_contacts": [ { "rank", "contact", "call_count", ... }, ... ],
  "central_nodes": [ { "node", "degree_centrality", "betweenness_centrality", "pagerank" }, ... ],
}
"""

from __future__ import annotations

from typing import Any

import networkx as nx
import pandas as pd

REQUIRED_COLS = frozenset({"caller", "callee", "call_time"})


def _canonical_pair(a: str, b: str) -> tuple[str, str]:
    x, y = str(a), str(b)
    return (x, y) if x <= y else (y, x)


def _parse_times(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", format="mixed")


def is_night_hour(ts: pd.Timestamp) -> bool:
    """深夜：22:00–次日 06:00（含 22:00，不含 06:00）。"""
    if pd.isna(ts):
        return False
    h = int(ts.hour)
    return h >= 22 or h < 6


def compute_night_call_ratio(df: pd.DataFrame) -> float:
    """全量记录的夜间通话占比。"""
    if df.empty or "call_time" not in df.columns:
        return 0.0
    t = _parse_times(df["call_time"])
    valid = t.notna()
    if not valid.any():
        return 0.0
    night = t[valid].map(is_night_hour)
    return float(night.sum() / len(night))


def top_contacts(
    df: pd.DataFrame,
    *,
    top_n: int = 10,
    perspective_number: str | None = None,
) -> list[dict[str, Any]]:
    """
    高频联系人：按通话次数 TOP N。

    - perspective_number 为 None：无向边聚合后，按双方对之间的总通话次数排名。
    - 指定主号码：仅统计该号码与各方的通话次数（对方为 contact）。
    """
    if df.empty or not REQUIRED_COLS.issubset(df.columns):
        return []

    sub = df[["caller", "callee"]].copy()
    sub["caller"] = sub["caller"].astype(str)
    sub["callee"] = sub["callee"].astype(str)

    if perspective_number is not None:
        pn = str(perspective_number)
        rows: list[tuple[str, str]] = []
        for _, r in sub.iterrows():
            if r["caller"] == pn:
                rows.append((pn, r["callee"]))
            elif r["callee"] == pn:
                rows.append((pn, r["caller"]))
        if not rows:
            return []
        cnt = pd.DataFrame(rows, columns=["_p", "contact"]).groupby("contact").size()
        cnt = cnt.sort_values(ascending=False).head(max(1, top_n))
        return [
            {"rank": i + 1, "contact": contact, "call_count": int(cnt[contact])}
            for i, contact in enumerate(cnt.index.tolist())
        ]

    # 无向对：A→B 与 B→A 合并为一对
    pairs: dict[tuple[str, str], int] = {}
    for _, r in sub.iterrows():
        u, v = _canonical_pair(r["caller"], r["callee"])
        pairs[(u, v)] = pairs.get((u, v), 0) + 1
    ranked = sorted(pairs.items(), key=lambda x: -x[1])[: max(1, top_n)]
    return [
        {
            "rank": i + 1,
            "party_a": a,
            "party_b": b,
            "call_count": c,
            "contact": f"{a}↔{b}",
        }
        for i, ((a, b), c) in enumerate(ranked)
    ]


def build_call_graph(df: pd.DataFrame) -> nx.Graph:
    """无向简单图，边权重为双方之间通话总次数。"""
    G = nx.Graph()
    if df.empty or not {"caller", "callee"}.issubset(df.columns):
        return G
    sub = df[["caller", "callee"]].copy()
    sub["caller"] = sub["caller"].astype(str)
    sub["callee"] = sub["callee"].astype(str)
    w: dict[tuple[str, str], float] = {}
    for _, r in sub.iterrows():
        u, v = _canonical_pair(r["caller"], r["callee"])
        w[(u, v)] = w.get((u, v), 0.0) + 1.0
    for (u, v), wt in w.items():
        G.add_edge(u, v, weight=wt)
    return G


def compute_centralities(
    G: nx.Graph,
    *,
    top_nodes: int | None = None,
) -> list[dict[str, Any]]:
    """
    Degree / Betweenness / PageRank。
    Betweenness 在拓扑结构上计算（忽略边权作为距离，避免将「通话次数」误当作路径长度）。
    PageRank 使用 weight 反映通话强度。
    """
    if G.number_of_nodes() == 0:
        return []

    dc = nx.degree_centrality(G)
    bc = nx.betweenness_centrality(G, normalized=True)
    pr = nx.pagerank(G, weight="weight", alpha=0.85)

    nodes = list(G.nodes())
    rows: list[dict[str, Any]] = []
    for n in nodes:
        rows.append(
            {
                "node": n,
                "degree_centrality": float(dc.get(n, 0.0)),
                "betweenness_centrality": float(bc.get(n, 0.0)),
                "pagerank": float(pr.get(n, 0.0)),
            }
        )
    # 关键中间人：Betweenness 优先，其次 PageRank、度中心性
    rows.sort(
        key=lambda x: (
            -x["betweenness_centrality"],
            -x["pagerank"],
            -x["degree_centrality"],
        )
    )
    if top_nodes is not None and top_nodes > 0:
        rows = rows[:top_nodes]
    return rows


def analyze_call_records(
    df: pd.DataFrame | None,
    *,
    top_contacts_n: int = 10,
    central_nodes_n: int | None = 15,
    perspective_number: str | None = None,
) -> dict[str, Any]:
    """
    汇总：深夜占比、TOP N 联系人、中心性节点。

    业务上可将「夜间通话占比 > 20%」作为异常模式：即 night_call_ratio > 0.2。
    """
    if df is None:
        df = pd.DataFrame()
    df = df.copy()
    if not df.empty and "call_time" in df.columns:
        df["call_time"] = _parse_times(df["call_time"])

    if not df.empty and not REQUIRED_COLS.issubset(df.columns):
        missing = REQUIRED_COLS - set(df.columns)
        raise ValueError(f"缺少列: {missing}")

    night_call_ratio = compute_night_call_ratio(df)
    contacts = top_contacts(
        df, top_n=top_contacts_n, perspective_number=perspective_number
    )
    G = build_call_graph(df)
    central = compute_centralities(G, top_nodes=central_nodes_n)

    return {
        "night_call_ratio": night_call_ratio,
        "top_contacts": contacts,
        "central_nodes": central,
    }


# ---------------------------------------------------------------------------
# 示例
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    demo = pd.DataFrame(
        [
            # 白天
            ("13800000001", "13900000002", "2024-06-01 10:30:00"),
            ("13800000001", "13900000002", "2024-06-01 11:00:00"),
            ("13800000001", "13900000003", "2024-06-01 14:00:00"),
            # 深夜（拉高夜间占比）
            ("13800000001", "13900000002", "2024-06-01 23:15:00"),
            ("13800000001", "13900000002", "2024-06-02 01:00:00"),
            ("13800000001", "13900000002", "2024-06-02 22:30:00"),
            ("13800000001", "13900000002", "2024-06-02 23:45:00"),
            ("13800000003", "13900000004", "2024-06-03 02:10:00"),
            # 中间人 13900000002：连接多方
            ("13900000002", "13800000001", "2024-06-04 09:00:00"),
            ("13900000002", "13900000005", "2024-06-04 10:00:00"),
            ("13900000002", "13900000006", "2024-06-04 11:00:00"),
        ],
        columns=["caller", "callee", "call_time"],
    )

    result = analyze_call_records(demo, top_contacts_n=5, central_nodes_n=8)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
