"""
微信/财付通调证样本：按文件名与列名识别 TenpayTrades / TenpayRegInfo。

- TenpayTrades：用户侧账号名称 → 对手侧账户名称（有向边，与借贷语义一致按行累计）。
- TenpayRegInfo：注册信息，不参与资金流构图（仅一期策略）。
"""

from __future__ import annotations

import re
from collections import defaultdict

import pandas as pd

from backend.app.services.tabular_fund_extract import (
    counterparty_agg_and_row_amounts_for_columns,
    pick_amount_column,
    pick_time_column,
)

def _norm_key(c: object) -> str:
    return str(c).strip().lower()


def _norm_col_map(df: pd.DataFrame) -> dict[str, str]:
    return {str(c).strip(): str(c) for c in df.columns}


def is_tenpay_reginfo_file(filename: str) -> bool:
    """注册信息表：不生成转账边。"""
    base = (filename or "").lower()
    return "tenpayreginfo" in re.sub(r"[_\s-]", "", base)


def is_tenpay_trades_file(filename: str) -> bool:
    base = (filename or "").lower()
    return "tenpaytrades" in re.sub(r"[_\s-]", "", base)


def _has_tenpay_trades_columns(df: pd.DataFrame) -> bool:
    keys = {str(c).strip() for c in df.columns}
    return "用户侧账号名称" in keys and "对手侧账户名称" in keys


def edges_from_tenpay_trades(df: pd.DataFrame) -> list[tuple[str, str, float]]:
    """财付通交易明细：有金额列时边权为同向金额合计（元）；否则为交易笔数。"""
    cmap = _norm_col_map(df)
    name_col = cmap.get("用户侧账号名称")
    cp_col = cmap.get("对手侧账户名称")
    if not name_col or not cp_col:
        return []
    amt_col = pick_amount_column(df)
    if amt_col is None:
        agg: dict[tuple[str, str], int] = defaultdict(int)
        for _, row in df.iterrows():
            s = str(row[name_col]).strip() if pd.notna(row[name_col]) else ""
            t = str(row[cp_col]).strip() if pd.notna(row[cp_col]) else ""
            if not s or not t or s == t:
                continue
            agg[(s, t)] += 1
        return [(a, b, float(w)) for (a, b), w in agg.items()]
    agg_amt: dict[tuple[str, str], float] = defaultdict(float)
    for _, row in df.iterrows():
        s = str(row[name_col]).strip() if pd.notna(row[name_col]) else ""
        t = str(row[cp_col]).strip() if pd.notna(row[cp_col]) else ""
        if not s or not t or s == t:
            continue
        v = row[amt_col]
        if pd.isna(v):
            continue
        try:
            amt = float(v)
        except (TypeError, ValueError):
            continue
        agg_amt[(s, t)] += amt
    return [(a, b, w) for (a, b), w in agg_amt.items()]


def should_use_tenpay_trades_adapter(filename: str, df: pd.DataFrame) -> bool:
    return is_tenpay_trades_file(filename) or _has_tenpay_trades_columns(df)


def tenpay_amount_row_stats_for_person(df: pd.DataFrame, person_id: str) -> tuple[float, int, bool]:
    """
    按「用户侧账号名称」匹配 person，汇总金额列并统计行数。
    返回 (金额合计, 行数, 是否存在可识别的金额列)。
    """
    cmap = _norm_col_map(df)
    name_col = cmap.get("用户侧账号名称")
    if not name_col:
        return 0.0, 0, False
    amt_col = pick_amount_column(df)
    has_amount_col = amt_col is not None
    pid = (person_id or "").strip()
    if not pid:
        return 0.0, 0, has_amount_col
    total = 0.0
    nrows = 0
    for _, row in df.iterrows():
        if str(row[name_col]).strip() != pid:
            continue
        nrows += 1
        if amt_col is None:
            continue
        v = row[amt_col]
        if pd.isna(v):
            continue
        try:
            total += float(v)
        except (TypeError, ValueError):
            continue
    return total, nrows, has_amount_col


def tenpay_amount_by_counterparty_for_person(
    df: pd.DataFrame, person_id: str
) -> list[tuple[str, float, int]]:
    """
    用户侧账号名称 == person 时，按对手侧账户名称汇总金额与笔数。
    无金额列或缺用户/对手列时返回空列表。
    """
    cmap = _norm_col_map(df)
    name_col = cmap.get("用户侧账号名称")
    cp_col = cmap.get("对手侧账户名称")
    if not name_col or not cp_col:
        return []
    amt_col = pick_amount_column(df)
    if amt_col is None:
        return []
    pid = (person_id or "").strip()
    if not pid:
        return []
    agg: dict[str, list] = defaultdict(lambda: [0.0, 0])
    for _, row in df.iterrows():
        if str(row[name_col]).strip() != pid:
            continue
        cp = str(row[cp_col]).strip() if pd.notna(row[cp_col]) else ""
        if not cp or cp == pid:
            continue
        v = row[amt_col]
        if pd.isna(v):
            continue
        try:
            amt = float(v)
        except (TypeError, ValueError):
            continue
        agg[cp][0] += amt
        agg[cp][1] += 1
    out = [(k, float(v[0]), int(v[1])) for k, v in agg.items()]
    out.sort(key=lambda x: (-x[1], x[0]))
    return out


def tenpay_counterparty_agg_and_row_amounts(
    df: pd.DataFrame, person_id: str
) -> tuple[
    list[tuple[str, float, int]],
    dict[str, list[tuple[float, str | None]]],
]:
    """
    与按对手汇总一致，并附带逐笔 (金额, 文档时间)（同对手多笔）。
    无金额列时返回 ([], {})。
    """
    cmap = _norm_col_map(df)
    name_col = cmap.get("用户侧账号名称")
    cp_col = cmap.get("对手侧账户名称")
    if not name_col or not cp_col:
        return [], {}
    amt_col = pick_amount_column(df)
    if amt_col is None:
        return [], {}
    tcol = pick_time_column(df)
    return counterparty_agg_and_row_amounts_for_columns(
        df, person_id, name_col, cp_col, amt_col, tcol, log_ctx="tenpay"
    )
