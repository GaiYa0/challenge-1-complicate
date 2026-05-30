"""
通用表格资金关系适配器（含 Tenpay 兼容）：

- 从多种表格列名中识别「用户侧/对手侧/金额/时间」字段；
- 统一输出资金边、人物金额统计、按对手逐笔聚合；
- Tenpay 列名与文件名仅作为兼容别名，不再作为唯一入口。
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


_USER_KEYS = frozenset(
    {
        "name",
        "姓名",
        "客户名称",
        "户名",
        "交易户名",
        "客户名",
        "账户名称",
        "用户侧账号名称",
        "用户侧",
        "付款人",
        "汇款人",
        "payer",
        "pay_user",
    }
)

_CP_KEYS = frozenset(
    {
        "counterparty",
        "counter_party",
        "对手",
        "交易对手",
        "对方",
        "对方户名",
        "对手方",
        "对方名称",
        "对手侧账户名称",
        "对手侧",
        "收款人",
        "receiver",
    }
)


def _pick_column(df: pd.DataFrame, candidates: frozenset[str]) -> str | None:
    for col in df.columns:
        k = _norm_key(col)
        if k in candidates:
            return str(col)
    for col in df.columns:
        k = _norm_key(col)
        for cand in candidates:
            if cand in k:
                return str(col)
    return None


def pick_user_column(df: pd.DataFrame) -> str | None:
    return _pick_column(df, _USER_KEYS)


def pick_counterparty_column(df: pd.DataFrame) -> str | None:
    return _pick_column(df, _CP_KEYS)


def is_registry_profile_file(filename: str) -> bool:
    """
    注册类信息表（仅档案属性，不参与资金边）。
    当前兼容 TenpayRegInfo 命名。
    """
    base = re.sub(r"[_\s-]", "", (filename or "").lower())
    if "tenpayreginfo" in base:
        return True
    return "注册信息" in (filename or "")


def is_fund_trade_file_name(filename: str) -> bool:
    """按文件名做“交易明细/资金流水”启发式判定。"""
    base = re.sub(r"[_\s-]", "", (filename or "").lower())
    hints = (
        "tenpaytrades",
        "trade",
        "trades",
        "transfer",
        "fund",
        "flow",
    )
    if any(h in base for h in hints):
        return True
    zh = filename or ""
    return any(k in zh for k in ("交易", "流水", "转账", "资金", "明细"))


def has_fund_edge_columns(df: pd.DataFrame) -> bool:
    return bool(pick_user_column(df) and pick_counterparty_column(df))


def can_extract_fund_edges(filename: str, df: pd.DataFrame) -> bool:
    if is_registry_profile_file(filename):
        return False
    return has_fund_edge_columns(df)


def edges_from_tabular_fund(df: pd.DataFrame) -> list[tuple[str, str, float]]:
    """
    通用资金边抽取：
    - 有金额列：边权按同向金额合计；
    - 无金额列：边权按交易笔数。
    """
    user_col = pick_user_column(df)
    cp_col = pick_counterparty_column(df)
    if not user_col or not cp_col:
        return []
    amt_col = pick_amount_column(df)
    if amt_col is None:
        agg_cnt: dict[tuple[str, str], int] = defaultdict(int)
        for _, row in df.iterrows():
            s = str(row[user_col]).strip() if pd.notna(row[user_col]) else ""
            t = str(row[cp_col]).strip() if pd.notna(row[cp_col]) else ""
            if not s or not t or s == t:
                continue
            agg_cnt[(s, t)] += 1
        return [(a, b, float(w)) for (a, b), w in agg_cnt.items()]
    agg_amt: dict[tuple[str, str], float] = defaultdict(float)
    for _, row in df.iterrows():
        s = str(row[user_col]).strip() if pd.notna(row[user_col]) else ""
        t = str(row[cp_col]).strip() if pd.notna(row[cp_col]) else ""
        if not s or not t or s == t:
            continue
        v = row[amt_col]
        if pd.isna(v):
            continue
        try:
            agg_amt[(s, t)] += float(v)
        except (TypeError, ValueError):
            continue
    return [(a, b, w) for (a, b), w in agg_amt.items()]


def amount_row_stats_for_person(
    df: pd.DataFrame, person_id: str
) -> tuple[float, int, bool, bool]:
    """
    返回 (金额合计, 行数, 是否存在金额列, 是否匹配到用户列)。
    """
    user_col = pick_user_column(df)
    if not user_col:
        return 0.0, 0, False, False
    amt_col = pick_amount_column(df)
    has_amount_col = amt_col is not None
    pid = (person_id or "").strip()
    if not pid:
        return 0.0, 0, has_amount_col, True
    total = 0.0
    nrows = 0
    for _, row in df.iterrows():
        if str(row[user_col]).strip() != pid:
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
    return total, nrows, has_amount_col, True


def counterparty_agg_and_row_amounts(
    df: pd.DataFrame, person_id: str
) -> tuple[
    list[tuple[str, float, int]],
    dict[str, list[tuple[float, str | None]]],
]:
    """
    对 person 作为用户侧的资金行，按对手方汇总金额与笔数，并保留逐笔(金额, 时间)。
    """
    user_col = pick_user_column(df)
    cp_col = pick_counterparty_column(df)
    if not user_col or not cp_col:
        return [], {}
    amt_col = pick_amount_column(df)
    if amt_col is None:
        return [], {}
    tcol = pick_time_column(df)
    return counterparty_agg_and_row_amounts_for_columns(
        df,
        person_id,
        user_col,
        cp_col,
        amt_col,
        tcol,
        log_ctx="tabular_graph_adapter",
    )
