"""
数据清洗与标准化引擎：将任意字段名的交易类 DataFrame 转为统一结构，供下游分析使用。

处理顺序（固定）：
1. 字段映射（自动别名 + 手动覆盖）
2. 去重（时间 + 账户 + 金额，联合主键；在**原始字符串**上比较，若需「格式统一后再去重」可再调用一次 `deduplicate_by_keys`）
3. 格式统一（时间 ISO 8601，金额 float 保留 2 位小数；时间解析优先 `format=\"mixed\"`）
4. 异常标记（不删行，is_anomaly + anomaly_reason）

输出：{ "clean_df": DataFrame, "report": dict }
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# 1) 字段映射：canonical -> 可能出现的别名（含中英文、常见缩写）
# ---------------------------------------------------------------------------

DEFAULT_CANONICAL_ALIASES: dict[str, list[str]] = {
    "txn_time": [
        "txn_time",
        "transaction_time",
        "trans_time",
        "datetime",
        "date_time",
        "时间",
        "交易时间",
        "交易日期时间",
        "日期时间",
        "转账时间",
        "发生时间",
        "timestamp",
        "ts",
    ],
    "account": [
        "account",
        "acct",
        "acct_no",
        "account_no",
        "账户",
        "账号",
        "客户账号",
        "本方账号",
        "银行卡号",
        "卡号",
        "户名账号",
    ],
    "amount": [
        "amount",
        "amt",
        "txn_amt",
        "交易金额",
        "金额",
        "发生金额",
        "转账金额",
        "借方金额",
        "贷方金额",
        "money",
        "value",
    ],
}

# 可选：业务类型 / 是否退款，用于「负数非退款」判断
DEFAULT_REFUND_ALIASES: dict[str, list[str]] = {
    "txn_type": [
        "txn_type",
        "type",
        "业务类型",
        "交易类型",
        "摘要",
        "备注",
    ],
}


def _norm_key(name: str) -> str:
    s = str(name).strip().lower()
    s = re.sub(r"\s+", "", s)
    s = s.replace("（", "(").replace("）", ")")
    return s


def _build_alias_lookup(
    canonical_aliases: dict[str, list[str]],
) -> dict[str, str]:
    """norm(别名) -> canonical，后写覆盖先写（manual 应在外部后应用）。"""
    lookup: dict[str, str] = {}
    for canonical, aliases in canonical_aliases.items():
        for a in aliases:
            lookup[_norm_key(a)] = canonical
        lookup[_norm_key(canonical)] = canonical
    return lookup


def resolve_column_mapping(
    columns: list[str] | pd.Index,
    *,
    manual_mapping: dict[str, str] | None = None,
    canonical_aliases: dict[str, list[str]] | None = None,
) -> dict[str, str]:
    """
    将原始列名映射到标准字段名。

    - manual_mapping: { 原始列名: canonical }，优先级最高。
    - 其余列按 canonical_aliases 自动匹配（列名规范化后命中别名表）。

    返回：{ 原始列名: canonical }，仅包含能解析的列；未匹配列不出现在 dict 中。
    """
    aliases = canonical_aliases or DEFAULT_CANONICAL_ALIASES
    lookup = _build_alias_lookup(aliases)
    out: dict[str, str] = {}

    if manual_mapping:
        for raw, can in manual_mapping.items():
            if raw in columns:
                out[str(raw)] = str(can)

    for col in columns:
        sc = str(col)
        if sc in out:
            continue
        nk = _norm_key(sc)
        if nk in lookup:
            out[sc] = lookup[nk]

    return out


def apply_column_mapping(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """
    只保留 mapping 中出现的列，并按 canonical 重命名。
    若多列映射到同一 canonical，按 mapping 迭代顺序取**首次出现**列。
    """
    pick: dict[str, str] = {}
    for raw, can in mapping.items():
        if raw not in df.columns:
            continue
        if can in pick:
            continue
        pick[can] = raw
    if not pick:
        return pd.DataFrame()
    sub = df[[pick[c] for c in pick]].copy()
    sub.columns = list(pick.keys())
    return sub


# ---------------------------------------------------------------------------
# 2) 去重
# ---------------------------------------------------------------------------


def deduplicate_by_keys(
    df: pd.DataFrame,
    *,
    subset: list[str] | None = None,
    keep: str = "first",
) -> tuple[pd.DataFrame, int]:
    """
    drop_duplicates。默认 subset = txn_time, account, amount（均须已存在）。
    返回 (去重后的 df, 删除行数)。
    """
    keys = subset or ["txn_time", "account", "amount"]
    missing = [k for k in keys if k not in df.columns]
    if missing:
        raise ValueError(f"去重缺少列: {missing}")
    before = len(df)
    out = df.drop_duplicates(subset=keys, keep=keep)
    removed = before - len(out)
    return out, removed


# ---------------------------------------------------------------------------
# 3) 格式统一
# ---------------------------------------------------------------------------


def normalize_formats(
    df: pd.DataFrame,
    *,
    time_col: str = "txn_time",
    amount_col: str = "amount",
) -> pd.DataFrame:
    """
    时间 -> pandas datetime 再格式化为 ISO 8601 字符串 YYYY-MM-DD HH:mm:ss（无时区按 naive）。
    金额 -> float，保留 2 位小数（仍用 float 存储；显示层可 format）。
    """
    out = df.copy()
    if time_col in out.columns:
        # pandas>=2.0 支持 format="mixed"，兼容多种手写日期/时间串
        try:
            ts = pd.to_datetime(out[time_col], errors="coerce", format="mixed")
        except (TypeError, ValueError):
            ts = pd.to_datetime(out[time_col], errors="coerce")
        out[time_col] = ts.dt.strftime("%Y-%m-%d %H:%M:%S")
    if amount_col in out.columns:
        ac = out[amount_col]
        if ac.dtype == object or str(ac.dtype) == "string":
            ac = (
                ac.astype(str)
                .str.replace(",", "", regex=False)
                .str.replace("，", "", regex=False)
                .str.strip()
            )
        out[amount_col] = pd.to_numeric(ac, errors="coerce").round(2)
    return out


# ---------------------------------------------------------------------------
# 4) 异常标记
# ---------------------------------------------------------------------------

_REFUND_TOKENS = frozenset(
    {
        "退",
        "退款",
        "冲正",
        "red",
        "refund",
        "rfd",
        "rev",
    },
)


def _row_looks_refund(type_val: Any) -> bool:
    if type_val is None or (isinstance(type_val, float) and np.isnan(type_val)):
        return False
    s = str(type_val).strip().lower()
    if not s:
        return False
    return any(t in s for t in _REFUND_TOKENS)


def mark_anomalies(
    df: pd.DataFrame,
    *,
    time_col: str = "txn_time",
    amount_col: str = "amount",
    txn_type_col: str | None = None,
    extreme_iqr_factor: float = 5.0,
    future_time_reference: datetime | None = None,
) -> pd.DataFrame:
    """
    不删行，增加：
    - is_anomaly: bool
    - anomaly_reason: str（多条用分号分隔）

    规则：
    - 负数金额且非退款语义 -> 异常
    - 时间解析失败（空）或未来时间 -> 异常
    - 金额缺失或极端值（IQR 外 factor 倍）-> 异常
    """
    out = df.copy()
    n = len(out)
    reasons: list[list[str]] = [[] for _ in range(n)]

    now = future_time_reference

    # 解析时间用于比较
    t_parsed = None
    if time_col in out.columns:
        t_raw = out[time_col]
        try:
            t_parsed = pd.to_datetime(t_raw, errors="coerce", format="mixed")
        except (TypeError, ValueError):
            t_parsed = pd.to_datetime(t_raw, errors="coerce")

    amt = out[amount_col] if amount_col in out.columns else pd.Series([np.nan] * n)

    # 退款语义（可选列）
    refund_flags = np.zeros(n, dtype=bool)
    if txn_type_col and txn_type_col in out.columns:
        for i, v in enumerate(out[txn_type_col].values):
            refund_flags[i] = _row_looks_refund(v)

    # 负数非退款
    for i in range(n):
        a = amt.iloc[i]
        if pd.isna(a):
            reasons[i].append("amount_missing")
            continue
        try:
            av = float(a)
        except (TypeError, ValueError):
            reasons[i].append("amount_invalid")
            continue
        if av < 0 and not refund_flags[i]:
            reasons[i].append("negative_amount_non_refund")

    # 时间
    if t_parsed is not None:
        for i in range(n):
            ts = t_parsed.iloc[i]
            if pd.isna(ts):
                reasons[i].append("time_parse_failed")
            else:
                t = pd.Timestamp(ts)
                if now is not None:
                    now_cmp = pd.Timestamp(now)
                elif t.tzinfo is not None:
                    now_cmp = pd.Timestamp.now(tz=t.tzinfo)
                else:
                    now_cmp = pd.Timestamp.now()
                if t > now_cmp:
                    reasons[i].append("future_time")

    # 极端金额（对非空数值；样本过少则跳过 IQR）
    valid_amt = pd.to_numeric(amt, errors="coerce")
    non_na = valid_amt.dropna()
    if len(non_na) >= 4:
        q1 = non_na.quantile(0.25)
        q3 = non_na.quantile(0.75)
        iqr = q3 - q1
        if pd.notna(iqr) and iqr > 0:
            low = float(q1 - extreme_iqr_factor * iqr)
            high = float(q3 + extreme_iqr_factor * iqr)
            for i in range(n):
                v = valid_amt.iloc[i]
                if pd.isna(v):
                    continue
                vf = float(v)
                if vf < low or vf > high:
                    reasons[i].append("extreme_amount")

    out["is_anomaly"] = [len(r) > 0 for r in reasons]
    out["anomaly_reason"] = [";".join(r) if r else "" for r in reasons]
    return out


# ---------------------------------------------------------------------------
# 流水线
# ---------------------------------------------------------------------------


def clean_and_standardize(
    df: pd.DataFrame,
    *,
    manual_mapping: dict[str, str] | None = None,
    canonical_aliases: dict[str, list[str]] | None = None,
    refund_type_column: str | None = None,
    manual_refund_mapping: dict[str, str] | None = None,
    extreme_iqr_factor: float = 5.0,
    dedupe_subset: list[str] | None = None,
) -> dict[str, Any]:
    """
    完整四步：映射 -> 去重 -> 格式 -> 异常。

    Parameters
    ----------
    manual_mapping
        原始列名 -> 标准名（如 {\"金额\": \"amount\"}）。
    refund_type_column
        原始列名，映射后会并入 canonical（若映射到 txn_type 则参与退款判断）。
    manual_refund_mapping
        若希望单独指定「退款列」原始名 -> txn_type，可写 {\"摘要\": \"txn_type\"}，
        并与 manual_mapping 合并。

    Returns
    -------
    { \"clean_df\": DataFrame, \"report\": { total, removed_duplicates, anomaly_count, mapped_columns, ... } }
    """
    if df is None or df.empty:
        return {
            "clean_df": pd.DataFrame(),
            "report": {
                "total": 0,
                "removed_duplicates": 0,
                "anomaly_count": 0,
                "rows_before_dedupe": 0,
                "mapped_columns": {},
            },
        }

    # 合并 manual：退款列可映射到 txn_type
    merged_manual = dict(manual_mapping or {})
    if manual_refund_mapping:
        merged_manual.update(manual_refund_mapping)

    mapping = resolve_column_mapping(
        df.columns,
        manual_mapping=merged_manual or None,
        canonical_aliases=canonical_aliases,
    )

    # 若用户声明 refund 原始列，但未在 auto 中出现，强制写入 mapping -> txn_type
    if refund_type_column and refund_type_column in df.columns:
        mapping[refund_type_column] = "txn_type"

    mapped = apply_column_mapping(df, mapping)
    rows_before_dedupe = len(mapped)

    # 核心三列必须存在才能继续
    required = {"txn_time", "account", "amount"}
    if not required.issubset(set(mapped.columns)):
        missing = required - set(mapped.columns)
        raise ValueError(
            f"映射后缺少必需列 {missing}。当前列: {list(mapped.columns)}。请补充 manual_mapping。",
        )

    deduped, removed = deduplicate_by_keys(mapped, subset=dedupe_subset)

    formatted = normalize_formats(deduped, time_col="txn_time", amount_col="amount")

    txn_type_col = "txn_type" if "txn_type" in formatted.columns else None
    with_flags = mark_anomalies(
        formatted,
        time_col="txn_time",
        amount_col="amount",
        txn_type_col=txn_type_col,
        extreme_iqr_factor=extreme_iqr_factor,
    )

    anomaly_count = int(with_flags["is_anomaly"].sum())

    report = {
        "total": len(with_flags),
        "removed_duplicates": removed,
        "anomaly_count": anomaly_count,
        "rows_before_dedupe": rows_before_dedupe,
        "mapped_columns": mapping,
    }

    return {"clean_df": with_flags, "report": report}


# ---------------------------------------------------------------------------
# 示例（可直接运行：python -m backend.data_platform.normalization_engine）
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    raw = pd.DataFrame(
        [
            ["2024-03-01 10:00:00", "622200", 1000.5, "转账"],
            ["2024-03-01 10:00:00", "622200", 1000.5, "转账"],  # 完全重复 -> 去重
            ["2024/03/01 10:00", "622200", "1,000.50", "转账"],  # 与首行同键（格式统一后）
            ["2024-03-01 10:00:00", "622200", 1000.5, "转账"],  # 再一条重复
            ["2024-03-02 12:00:00", "622201", "-500", "退款"],  # 负数+退款 -> 不标异常（仅负非退款）
            ["2030-01-01 00:00:00", "622201", "100.0", "转账"],  # 未来时间
            ["bad-date", "622201", "999999999", "转账"],  # 时间解析失败 + 极端金额
        ],
        columns=["交易时间", "客户账号", "交易金额", "摘要"],
    )

    result = clean_and_standardize(
        raw,
        manual_mapping=None,
        refund_type_column="摘要",
    )

    print("=== report ===")
    print(result["report"])
    print("\n=== clean_df ===")
    print(result["clean_df"].to_string())
