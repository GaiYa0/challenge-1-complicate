"""
案件维度图谱：从「本案 dataset=case-{id}」下的表格文件构建资金关系边。

支持通用列识别（含 Tenpay 别名兼容）；注册信息类表不生成资金流边。
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from typing import Any

import pandas as pd
from minio import Minio
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.infra import minio_client as minio_ops
from backend.app.repositories import file_repo
from backend.app.schemas.graph import (
    GraphDegreeItem,
    GraphVisualizationData,
    GraphVisualizationEdge,
    GraphVisualizationNode,
)
from backend.app.services import graph_controlled_service, tabular_graph_adapter
from backend.app.services.file_service import read_tabular_bytes_to_dataframe

logger = logging.getLogger(__name__)

def _edges_for_case_file(filename: str, df: pd.DataFrame) -> list[tuple[str, str, float]]:
    if tabular_graph_adapter.is_registry_profile_file(filename):
        logger.info("case_graph_skip_registry_profile filename=%s", filename)
        return []
    if not tabular_graph_adapter.can_extract_fund_edges(filename, df):
        logger.info(
            "case_graph_adapter kind=no_fund_columns filename=%s cols=%s",
            filename,
            list(df.columns)[:20],
        )
        return []
    edges = tabular_graph_adapter.edges_from_tabular_fund(df)
    logger.info(
        "case_graph_adapter kind=tabular_fund filename=%s edge_count=%s cols=%s",
        filename,
        len(edges),
        list(df.columns)[:20],
    )
    return edges


def case_graph_cache_signature(db: Session, tenant_user_id: int, case_id: int) -> str:
    """本案表格文件集合签名，用于 Redis 缓存键（换文件/增删后失效）。"""
    files = file_repo.list_tabular_files_for_case_dataset(
        db, tenant_user_id=tenant_user_id, case_id=case_id
    )
    if not files:
        return "empty"
    parts = [
        f"{f.id}:{f.filename}:{f.created_at.isoformat() if f.created_at else ''}"
        for f in files
    ]
    return hashlib.sha256("\n".join(sorted(parts)).encode("utf-8")).hexdigest()[:16]


def load_case_transfer_edges(
    db: Session,
    minio: Minio,
    *,
    tenant_user_id: int,
    case_id: int,
) -> list[tuple[str, str, float]]:
    files = file_repo.list_tabular_files_for_case_dataset(
        db, tenant_user_id=tenant_user_id, case_id=case_id
    )
    if not files:
        logger.info("case_graph_no_tabular_files case_id=%s", case_id)
        return []
    merged: dict[tuple[str, str], float] = defaultdict(float)
    for f in files:
        fn = f.filename or ""
        try:
            raw = minio_ops.get_bytes(minio, f.bucket_name, f.object_name)
            df = read_tabular_bytes_to_dataframe(fn, raw)
            for s, t, w in _edges_for_case_file(fn, df):
                merged[(s, t)] += w
        except Exception:
            logger.exception("case_tabular_read_failed filename=%s", fn)
    out = [(s, t, w) for (s, t), w in merged.items()]
    logger.info(
        "case_graph_loaded case_id=%s file_count=%s total_edges=%s",
        case_id,
        len(files),
        len(out),
    )
    return out


def node_set_from_edges(edges: list[tuple[str, str, float]]) -> set[str]:
    """边表端点集合（与构图侧 name/counterparty 字符串一致，已 strip）。"""
    out: set[str] = set()
    for s, t, _ in edges:
        if s:
            out.add(s)
        if t:
            out.add(t)
    return out


def transfer_counts_for_person(
    person_id: str, edges: list[tuple[str, str, float]]
) -> tuple[int, int]:
    """有向边统计：转出条数、转入条数（合并后的每条边计 1）。"""
    pid = person_id.strip()
    if not pid:
        return 0, 0
    out_c, in_c = 0, 0
    for s, t, _ in edges:
        if s == pid:
            out_c += 1
        if t == pid:
            in_c += 1
    return out_c, in_c


def ego_graph_visualization_from_edges(
    edges: list[tuple[str, str, float]],
    center: str,
    max_edges: int = 60,
) -> GraphVisualizationData:
    """中心点一跳：保留与 center 相关的有向边（最多 max_edges 条），用于画像社交子图。"""
    center = center.strip()
    if not center:
        return GraphVisualizationData(nodes=[], edges=[])

    picked: list[tuple[str, str]] = []
    for s, t, _ in edges:
        if s != center and t != center:
            continue
        if len(picked) >= max_edges:
            break
        picked.append((s, t))

    if not picked:
        return GraphVisualizationData(
            nodes=[GraphVisualizationNode(id=center, label=center)],
            edges=[],
        )

    node_set: set[str] = {center}
    edges_out: list[GraphVisualizationEdge] = []
    for ei, (s, t) in enumerate(picked):
        node_set.add(s)
        node_set.add(t)
        edges_out.append(GraphVisualizationEdge(id=f"e{ei}", source=s, target=t))
    nodes = [GraphVisualizationNode(id=k, label=k) for k in sorted(node_set)]
    return GraphVisualizationData(nodes=nodes, edges=edges_out)


def person_in_case_tabular_graph(
    db: Session,
    minio: Minio,
    *,
    tenant_user_id: int,
    case_id: int,
    person_id: str,
    edges: list[tuple[str, str, float]] | None = None,
) -> bool:
    """人物是否出现在本案表格构图边端点（可选传入已加载边集避免重复读 MinIO）。"""
    pid = (person_id or "").strip()
    if not pid:
        return False
    if edges is None:
        edges = load_case_transfer_edges(
            db, minio, tenant_user_id=tenant_user_id, case_id=case_id
        )
    return pid in node_set_from_edges(edges)


def aggregate_tabular_amount_and_rows_for_person(
    db: Session,
    minio: Minio,
    *,
    tenant_user_id: int,
    case_id: int,
    person_id: str,
) -> tuple[float | None, int]:
    """
    遍历本案可识别资金表，汇总 person 作为用户侧的交易金额与行数。
    无匹配行返回 (None, 0)；有行但无金额列返回 (None, 行数)，由画像回退合成金额。
    """
    files = file_repo.list_tabular_files_for_case_dataset(
        db, tenant_user_id=tenant_user_id, case_id=case_id
    )
    total_sum = 0.0
    total_rows = 0
    saw_amount_col = False
    for f in files:
        fn = f.filename or ""
        try:
            raw = minio_ops.get_bytes(minio, f.bucket_name, f.object_name)
            df = read_tabular_bytes_to_dataframe(fn, raw)
            if tabular_graph_adapter.is_registry_profile_file(fn):
                continue
            amt, rows, has_col, matched = tabular_graph_adapter.amount_row_stats_for_person(df, person_id)
            if not matched:
                continue
            total_rows += rows
            total_sum += amt
            if has_col:
                saw_amount_col = True
        except Exception:
            logger.exception("case_tabular_amount_scan_failed filename=%s", fn)
    if total_rows == 0:
        return None, 0
    if not saw_amount_col:
        return None, total_rows
    return total_sum, total_rows


MAX_FUND_TX_ROWS_PER_COUNTERPARTY = 400
MAX_FUND_TX_ROWS_TOTAL = 2000


def _earliest_latest_from_tuples(
    items: list[tuple[float, str | None]],
) -> tuple[str | None, str | None]:
    times = [t for _, t in items if t]
    if not times:
        return None, None
    dts: list[tuple[pd.Timestamp, str]] = []
    for t in times:
        dt = pd.to_datetime(t, errors="coerce")
        if pd.isna(dt):
            continue
        dts.append((dt, t))
    if not dts:
        return min(times, key=str), max(times, key=str)
    dts.sort(key=lambda x: x[0])
    return dts[0][1], dts[-1][1]


def _cap_fund_tx_rows(
    rows_by_cp: dict[str, list[tuple[float, str | None]]],
) -> dict[str, list[tuple[float, str | None]]]:
    """逐笔 (金额, 时间)：每对手上限 + 全局上限。"""
    per_cp = {
        k: v[:MAX_FUND_TX_ROWS_PER_COUNTERPARTY] for k, v in rows_by_cp.items()
    }
    out: dict[str, list[tuple[float, str | None]]] = {}
    n = 0
    for cp in sorted(per_cp.keys(), key=lambda c: -sum(p[0] for p in per_cp[c])):
        chunk: list[tuple[float, str | None]] = []
        for item in per_cp[cp]:
            if n >= MAX_FUND_TX_ROWS_TOTAL:
                break
            chunk.append(item)
            n += 1
        if chunk:
            out[cp] = chunk
        if n >= MAX_FUND_TX_ROWS_TOTAL:
            break
    return out


def aggregate_tabular_fund_lines_for_person(
    db: Session,
    minio: Minio,
    *,
    tenant_user_id: int,
    case_id: int,
    person_id: str,
) -> tuple[
    list[tuple[str, float, int]],
    dict[str, list[tuple[float, str | None]]],
    dict[str, tuple[str | None, str | None]],
]:
    """
    跨本案表格文件，按对手合并金额、笔数与逐笔 (金额, 文档时间)：
    - 通用字段识别（含 Tenpay 别名兼容）统一解析；
    - 注册信息类表自动跳过。
    并做上限截断；返回每对手全量数据的最早/最晚时间。
    """
    merged: dict[str, list[float | int]] = defaultdict(lambda: [0.0, 0])
    merged_rows: dict[str, list[tuple[float, str | None]]] = defaultdict(list)
    files = file_repo.list_tabular_files_for_case_dataset(
        db, tenant_user_id=tenant_user_id, case_id=case_id
    )
    for f in files:
        fn = f.filename or ""
        try:
            raw = minio_ops.get_bytes(minio, f.bucket_name, f.object_name)
            df = read_tabular_bytes_to_dataframe(fn, raw)
            if tabular_graph_adapter.is_registry_profile_file(fn):
                continue
            agg_rows, rows_dict = tabular_graph_adapter.counterparty_agg_and_row_amounts(df, person_id)
            if not agg_rows:
                continue
            logger.info(
                "case_fund_lines_adapter kind=tabular filename=%s lines=%s",
                fn,
                len(agg_rows),
            )
            for cp, amt, cnt in agg_rows:
                merged[cp][0] += amt
                merged[cp][1] += cnt
            for cp, pairs in rows_dict.items():
                merged_rows[cp].extend(pairs)
        except Exception:
            logger.exception("case_tabular_fund_lines_failed filename=%s", fn)
    out = [(k, float(v[0]), int(v[1])) for k, v in merged.items()]
    out.sort(key=lambda x: (-x[1], x[0]))
    time_bounds: dict[str, tuple[str | None, str | None]] = {
        cp: _earliest_latest_from_tuples(merged_rows[cp]) for cp in merged_rows
    }
    row_map = _cap_fund_tx_rows(dict(merged_rows))
    return out, row_map, time_bounds


def aggregate_tenpay_amount_and_rows_for_person(
    db: Session,
    minio: Minio,
    *,
    tenant_user_id: int,
    case_id: int,
    person_id: str,
) -> tuple[float | None, int]:
    """兼容旧函数名，实际走通用表格实现。"""
    return aggregate_tabular_amount_and_rows_for_person(
        db,
        minio,
        tenant_user_id=tenant_user_id,
        case_id=case_id,
        person_id=person_id,
    )


def aggregate_tenpay_fund_lines_for_person(
    db: Session,
    minio: Minio,
    *,
    tenant_user_id: int,
    case_id: int,
    person_id: str,
) -> tuple[
    list[tuple[str, float, int]],
    dict[str, list[tuple[float, str | None]]],
    dict[str, tuple[str | None, str | None]],
]:
    """兼容旧函数名，实际走通用表格实现。"""
    return aggregate_tabular_fund_lines_for_person(
        db,
        minio,
        tenant_user_id=tenant_user_id,
        case_id=case_id,
        person_id=person_id,
    )


def _clip_viz(
    data: GraphVisualizationData, node_cap: int
) -> GraphVisualizationData:
    if len(data.nodes) <= node_cap:
        return data
    kept_ids = {n.id for n in data.nodes[:node_cap]}
    edges2 = [e for e in data.edges if e.source in kept_ids and e.target in kept_ids]
    return GraphVisualizationData(nodes=data.nodes[:node_cap], edges=edges2)


def build_visualization_for_case(
    db: Session,
    minio: Minio,
    *,
    tenant_user_id: int,
    case_id: int,
    edge_limit: int = 500,
    node_cap: int | None = None,
) -> GraphVisualizationData:
    edges = load_case_transfer_edges(db, minio, tenant_user_id=tenant_user_id, case_id=case_id)
    if not edges:
        return GraphVisualizationData(nodes=[], edges=[])
    if node_cap is None:
        node_cap = get_settings().GRAPH_NODE_CAP
    lim = max(1, min(int(edge_limit), 5000))
    edges_sorted = sorted(edges, key=lambda x: x[2], reverse=True)[:lim]
    node_set: dict[str, str] = {}
    edges_out: list[GraphVisualizationEdge] = []
    seen: set[tuple[str, str]] = set()
    ei = 0
    for s, t, w in edges_sorted:
        pair = (s, t)
        if pair in seen:
            continue
        seen.add(pair)
        node_set[s] = s
        node_set[t] = t
        edges_out.append(
            GraphVisualizationEdge(
                id=f"e{ei}", source=s, target=t, weight=round(float(w), 2)
            )
        )
        ei += 1
    nodes = [GraphVisualizationNode(id=k, label=v) for k, v in sorted(node_set.items())]
    raw = GraphVisualizationData(nodes=nodes, edges=edges_out)
    return _clip_viz(raw, max(1, int(node_cap)))


def out_degree_for_case(
    db: Session,
    minio: Minio,
    *,
    tenant_user_id: int,
    case_id: int,
) -> list[GraphDegreeItem]:
    edges = load_case_transfer_edges(db, minio, tenant_user_id=tenant_user_id, case_id=case_id)
    if not edges:
        return []
    out_c: dict[str, int] = defaultdict(int)
    for s, t, _ in edges:
        if s != t:
            out_c[s] += 1
    rows = sorted(out_c.items(), key=lambda x: (-x[1], x[0]))
    return [GraphDegreeItem(name=n, degree=d) for n, d in rows]


def build_controlled_graph_for_case(
    db: Session,
    minio: Minio,
    *,
    tenant_user_id: int,
    case_id: int,
    person_id: str | None,
    depth: int,
    limit: int,
    include_centrality: bool,
) -> dict[str, Any]:
    all_edges = load_case_transfer_edges(db, minio, tenant_user_id=tenant_user_id, case_id=case_id)
    if not all_edges:
        return {"nodes": [], "edges": []}
    node_cap = max(1, min(limit, 100))
    depth_cap = max(1, min(depth, 8))
    return graph_controlled_service.build_controlled_from_directed_edges(
        all_edges,
        person_id=person_id,
        depth_cap=depth_cap,
        node_cap=node_cap,
        include_centrality=include_centrality,
        driver=None,
        tenant_id=None,
    )
