"""
案件表格中「用户侧/对手/金额/时间」列探测与按对手逐笔汇总。

供财付通专用表与「通用 name/cp 列 + 金额」表共用，输出结构与 tenpay 逐笔一致。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# 与 case_graph_service._NAME_KEYS / _CP_KEYS 保持语义一致，修改时请同步
_NAME_KEYS: frozenset[str] = frozenset(
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
    }
)
_CP_KEYS: frozenset[str] = frozenset(
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
    }
)

_AMOUNT_NAME_CANDIDATES: tuple[str, ...] = (
    "交易金额",
    "金额",
    "发生金额",
    "订单金额",
    "转账金额",
    "借方金额",
    "贷方金额",
)

_TIME_NAME_CANDIDATES: tuple[str, ...] = (
    "交易时间",
    "交易发生时间",
    "发生时间",
    "创建时间",
    "记账日期",
    "交易日期",
    "日期",
    "时间",
)


def _norm_key(c: object) -> str:
    return str(c).strip().lower()


def _norm_col_map(df: pd.DataFrame) -> dict[str, str]:
    return {str(c).strip(): str(c) for c in df.columns}


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


def pick_amount_column(df: pd.DataFrame) -> str | None:
    cmap = _norm_col_map(df)
    for cand in _AMOUNT_NAME_CANDIDATES:
        if cand in cmap:
            return cmap[cand]
    for col in df.columns:
        k = _norm_key(col)
        if "金额" in k:
            return str(col)
        if "amount" in k:
            return str(col)
    return None


def pick_time_column(df: pd.DataFrame) -> str | None:
    cmap = _norm_col_map(df)
    for cand in _TIME_NAME_CANDIDATES:
        if cand in cmap:
            return cmap[cand]
    for col in df.columns:
        k = _norm_key(col)
        if "时间" in k or "日期" in k:
            return str(col)
    return None


def parse_tx_time_cell(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    if isinstance(val, str) and not str(val).strip():
        return None
    t = pd.to_datetime(val, errors="coerce")
    if pd.isna(t):
        return None
    try:
        s = pd.Timestamp(t).isoformat()
    except Exception:
        return None
    if "T" in s or "+" in s:
        return s.replace("+00:00", "")[:19]
    return s[:10]


def pick_generic_name_column(df: pd.DataFrame) -> str | None:
    return _pick_column(df, _NAME_KEYS)


def pick_generic_cp_column(df: pd.DataFrame) -> str | None:
    return _pick_column(df, _CP_KEYS)


def can_extract_generic_fund_rows(df: pd.DataFrame) -> bool:
    """有用户侧/对手/金额三列时即可逐笔资金聚合（时间可选）。"""
    n = pick_generic_name_column(df)
    c = pick_generic_cp_column(df)
    a = pick_amount_column(df)
    return bool(n and c and a)


def counterparty_agg_and_row_amounts_for_columns(
    df: pd.DataFrame,
    person_id: str,
    name_col: str,
    cp_col: str,
    amt_col: str,
    time_col: str | None,
    *,
    log_ctx: str = "",
) -> tuple[
    list[tuple[str, float, int]],
    dict[str, list[tuple[float, str | None]]],
]:
    """
    按行汇总：与 tenpay 逐笔结构一致。仅统计 name_col == person 的行。
    """
    pid = (person_id or "").strip()
    if not pid:
        return [], {}
    agg: dict[str, list] = defaultdict(lambda: [0.0, 0])
    rows_by_cp: dict[str, list[tuple[float, str | None]]] = defaultdict(list)
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
        tstr: str | None = None
        if time_col:
            try:
                tstr = parse_tx_time_cell(row[time_col])
            except (KeyError, TypeError, ValueError):
                tstr = None
        agg[cp][0] += amt
        agg[cp][1] += 1
        rows_by_cp[cp].append((amt, tstr))
    out = [(k, float(v[0]), int(v[1])) for k, v in agg.items()]
    out.sort(key=lambda x: (-x[1], x[0]))
    if log_ctx and out:
        logger.info(
            "tabular_fund_extract rows name=%s cp=%s amt=%s time=%s ctx=%s cpairs=%s",
            name_col,
            cp_col,
            amt_col,
            time_col,
            log_ctx,
            len(out),
        )
    return out, dict(rows_by_cp)


def try_generic_fund_aggregation(
    df: pd.DataFrame,
    person_id: str,
    *,
    log_ctx: str = "",
) -> tuple[
    list[tuple[str, float, int]],
    dict[str, list[tuple[float, str | None]]],
] | None:
    """
    用通用列名（与构图 _edges_from_dataframe 一致）+ 金额 + 可选时间 做逐笔聚合。
    列不全时返回 None，不抛错。
    """
    if not can_extract_generic_fund_rows(df):
        return None
    n = pick_generic_name_column(df)
    c = pick_generic_cp_column(df)
    a = pick_amount_column(df)
    if not n or not c or not a:
        return None
    tc = pick_time_column(df)
    return counterparty_agg_and_row_amounts_for_columns(
        df, person_id, n, c, a, tc, log_ctx=log_ctx or "generic"
    )
