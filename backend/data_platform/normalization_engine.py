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


# ==================== Enhanced Recognition Overrides ====================

from rapidfuzz import fuzz  # noqa: E402

STANDARD_COLUMNS = ("from_user", "to_user", "amount", "timestamp", "location")
FIELD_ALIAS_DICT: dict[str, list[str]] = {
    "from_user": ["from_user", "from", "payer", "pay_user", "付款人", "汇款人", "转账人", "付款方"],
    "to_user": ["to_user", "to", "receiver", "payee", "counterparty", "收款人", "对手方", "收款方"],
    "amount": ["amount", "amt", "money", "value", "交易金额", "金额", "发生金额", "转账金额"],
    "timestamp": ["timestamp", "time", "trade_time", "txn_time", "transaction_time", "时间", "交易时间", "转账时间"],
    "location": ["location", "place", "addr", "地址", "地点", "交易地点"],
    "phone": ["phone", "mobile", "手机号", "手机"],
    "id_card": ["id_card", "身份证", "身份证号"],
    "bank_card": ["bank_card", "card_no", "银行卡", "银行卡号", "卡号"],
    "latitude": ["lat", "latitude", "纬度"],
    "longitude": ["lng", "lon", "longitude", "经度"],
    "address": ["address", "addr", "住址", "详细地址"],
    "name": ["name", "fullname", "姓名", "户名", "用户名"],
    "txn_type": ["txn_type", "type", "业务类型", "交易类型", "摘要", "备注"],
}
_MAPPING_CACHE: dict[str, dict[str, str]] = {}
_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
_ID_RE = re.compile(r"^\d{17}[\dXx]$")
_BANK_RE = re.compile(r"^\d{12,19}$")
_TIME_RE = re.compile(r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}")
_LAT_RE = re.compile(r"^-?\d{1,2}\.\d+$")
_LNG_RE = re.compile(r"^-?\d{1,3}\.\d+$")


def invalidate_mapping_cache(*, key: str | None = None, prefix: str | None = None) -> int:
    """
    清理字段映射的进程内缓存：
    - key: 清理单条
    - prefix: 清理前缀匹配的多条
    返回删除条数。
    """
    if key:
        return 1 if _MAPPING_CACHE.pop(str(key), None) is not None else 0
    if prefix is None:
        n = len(_MAPPING_CACHE)
        _MAPPING_CACHE.clear()
        return n
    pref = str(prefix)
    keys = [k for k in list(_MAPPING_CACHE.keys()) if k.startswith(pref)]
    for k in keys:
        _MAPPING_CACHE.pop(k, None)
    return len(keys)


def _norm_key_v2(name: str) -> str:
    s = str(name or "").strip().lower()
    s = s.replace("（", "(").replace("）", ")")
    return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", s)


def _preprocess_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    out = out.dropna(axis=0, how="all").dropna(axis=1, how="all")
    cols: list[str] = []
    seen: dict[str, int] = {}
    for i, c in enumerate(out.columns):
        base = str(c or "").strip()
        if not base or base.lower() == "nan":
            base = f"col_{i+1}"
        base = re.sub(r"\s+", " ", base).strip()
        idx = seen.get(base, 0) + 1
        seen[base] = idx
        cols.append(base if idx == 1 else f"{base}_{idx}")
    out.columns = cols
    for col in out.columns:
        if out[col].dtype == object or str(out[col].dtype) == "string":
            out[col] = out[col].astype(str).replace("nan", "").fillna("").str.strip()
    return out.reset_index(drop=True)


def _score_by_content(series: pd.Series, canonical: str) -> float:
    vals = series.dropna().astype(str)
    vals = vals[vals.str.strip() != ""].head(256)
    if vals.empty:
        return 0.0
    total = len(vals)
    if canonical == "amount":
        parsed = (
            vals.str.replace(r"[￥¥,\s，]|人民币", "", regex=True)
            .pipe(pd.to_numeric, errors="coerce")
            .notna()
            .sum()
        )
        return float(parsed) / float(total) * 100.0
    if canonical == "timestamp":
        parsed = pd.to_datetime(vals, errors="coerce", format="mixed").notna().sum()
        return float(parsed) / float(total) * 100.0
    if canonical == "phone":
        return float(vals.str.match(_PHONE_RE).sum()) / float(total) * 100.0
    if canonical == "id_card":
        return float(vals.str.match(_ID_RE).sum()) / float(total) * 100.0
    if canonical == "bank_card":
        return float(vals.str.match(_BANK_RE).sum()) / float(total) * 100.0
    if canonical == "latitude":
        return float(vals.str.match(_LAT_RE).sum()) / float(total) * 100.0
    if canonical == "longitude":
        return float(vals.str.match(_LNG_RE).sum()) / float(total) * 100.0
    if canonical == "location":
        h = vals.str.contains(r"路|街|区|镇|村|大道|号|省|市", regex=True).sum()
        return float(h) / float(total) * 100.0
    if canonical in {"from_user", "to_user", "name"}:
        h = vals.str.match(r"^[\u4e00-\u9fffA-Za-z]{2,20}$").sum()
        return float(h) / float(total) * 100.0
    return 0.0


def _resolve_mapping_v2(
    df: pd.DataFrame,
    *,
    manual_mapping: dict[str, str] | None = None,
    learned_mapping: dict[str, str] | None = None,
    alias_dict: dict[str, list[str]] | None = None,
    name_weight: float = 0.7,
    content_weight: float = 0.3,
    min_score: float = 55.0,
) -> tuple[dict[str, str], dict[str, dict[str, float]]]:
    active_alias_dict = alias_dict or FIELD_ALIAS_DICT
    cols = [str(c) for c in df.columns]
    mapping: dict[str, str] = {}
    scores: dict[str, dict[str, float]] = {}

    if manual_mapping:
        for raw, can in manual_mapping.items():
            if raw in df.columns and can in active_alias_dict:
                mapping[str(raw)] = str(can)
                scores[str(raw)] = {"name": 100.0, "content": 100.0, "final": 100.0}

    if learned_mapping:
        for raw, can in learned_mapping.items():
            if raw in df.columns and raw not in mapping and can in active_alias_dict:
                mapping[str(raw)] = str(can)
                scores[str(raw)] = {"name": 95.0, "content": 80.0, "final": 90.5}

    used_can = set(mapping.values())
    for col in cols:
        if col in mapping:
            continue
        norm_col = _norm_key_v2(col)
        best_can = None
        best_name = 0.0
        best_content = 0.0
        best_final = 0.0
        for can, aliases in active_alias_dict.items():
            if can in used_can and can in STANDARD_COLUMNS:
                continue
            alias_scores = [float(fuzz.WRatio(norm_col, _norm_key_v2(a))) for a in (aliases + [can])]
            name_sc = max(alias_scores) if alias_scores else 0.0
            content_sc = _score_by_content(df[col], can)
            final_sc = name_weight * name_sc + content_weight * content_sc
            if final_sc > best_final:
                best_can, best_name, best_content, best_final = can, name_sc, content_sc, final_sc
        if best_can and best_final >= min_score:
            mapping[col] = best_can
            used_can.add(best_can)
            scores[col] = {"name": round(best_name, 2), "content": round(best_content, 2), "final": round(best_final, 2)}

    return mapping, scores


def _apply_mapping_v2(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    picks: dict[str, str] = {}
    for raw, can in mapping.items():
        if raw in df.columns and can not in picks:
            picks[can] = raw
    out = pd.DataFrame()
    for can in FIELD_ALIAS_DICT:
        if can in picks:
            out[can] = df[picks[can]]
    for can in STANDARD_COLUMNS:
        if can not in out.columns:
            if can == "amount":
                out[can] = 0.0
            else:
                out[can] = ""
    if "timestamp" in out.columns:
        ts = pd.to_datetime(out["timestamp"], errors="coerce", format="mixed")
        out["timestamp"] = ts.dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")
    if "amount" in out.columns:
        out["amount"] = (
            out["amount"].astype(str).str.replace(r"[￥¥,\s，]|人民币", "", regex=True)
        )
        out["amount"] = pd.to_numeric(out["amount"], errors="coerce").fillna(0.0).round(2)
    for c in ("from_user", "to_user", "location"):
        out[c] = out[c].astype(str).replace("nan", "").fillna("").str.strip()
    out["txn_time"] = out["timestamp"]
    out["account"] = out["from_user"]
    return out


def clean_and_standardize(
    df: pd.DataFrame,
    *,
    manual_mapping: dict[str, str] | None = None,
    canonical_aliases: dict[str, list[str]] | None = None,
    refund_type_column: str | None = None,
    manual_refund_mapping: dict[str, str] | None = None,
    extreme_iqr_factor: float = 5.0,
    dedupe_subset: list[str] | None = None,
    learned_mapping: dict[str, str] | None = None,
    mapping_cache_key: str | None = None,
    name_weight: float = 0.7,
    content_weight: float = 0.3,
    min_match_score: float = 55.0,
) -> dict[str, Any]:
    if df is None or df.empty:
        return {
            "clean_df": pd.DataFrame(columns=list(STANDARD_COLUMNS)),
            "report": {
                "total": 0,
                "removed_duplicates": 0,
                "anomaly_count": 0,
                "rows_before_dedupe": 0,
                "mapped_columns": {},
                "mapping_scores": {},
            },
        }
    src = _preprocess_dataframe(df)
    merged_manual = dict(manual_mapping or {})
    if manual_refund_mapping:
        merged_manual.update(manual_refund_mapping)
    if refund_type_column and refund_type_column in src.columns:
        merged_manual[str(refund_type_column)] = "txn_type"
    alias_dict = {k: list(v) for k, v in FIELD_ALIAS_DICT.items()}
    if canonical_aliases:
        for can, aliases in canonical_aliases.items():
            alias_dict.setdefault(str(can), [])
            alias_dict[str(can)].extend(str(a) for a in (aliases or []))
    cache_hit = False
    mapping: dict[str, str]
    mapping_scores: dict[str, dict[str, float]]
    if mapping_cache_key and mapping_cache_key in _MAPPING_CACHE:
        mapping = dict(_MAPPING_CACHE[mapping_cache_key])
        mapping_scores = {}
        cache_hit = True
    else:
        mapping, mapping_scores = _resolve_mapping_v2(
            src,
            manual_mapping=merged_manual or None,
            learned_mapping=learned_mapping,
            alias_dict=alias_dict,
            name_weight=name_weight,
            content_weight=content_weight,
            min_score=min_match_score,
        )
        if mapping_cache_key:
            _MAPPING_CACHE[mapping_cache_key] = dict(mapping)

    mapped = _apply_mapping_v2(src, mapping)
    unresolved_required = [c for c in STANDARD_COLUMNS if c not in set(mapping.values())]
    rows_before_dedupe = len(mapped)
    dedupe_keys = dedupe_subset or ["timestamp", "from_user", "to_user", "amount"]
    dedupe_keys = [k for k in dedupe_keys if k in mapped.columns]
    if dedupe_keys:
        deduped = mapped.drop_duplicates(subset=dedupe_keys, keep="first")
        removed = int(len(mapped) - len(deduped))
    else:
        deduped, removed = mapped, 0
    flagged = mark_anomalies(
        deduped,
        time_col="timestamp",
        amount_col="amount",
        txn_type_col="txn_type" if "txn_type" in deduped.columns else None,
        extreme_iqr_factor=extreme_iqr_factor,
    )
    anomaly_count = int(flagged["is_anomaly"].sum()) if "is_anomaly" in flagged.columns else 0
    report = {
        "total": len(flagged),
        "removed_duplicates": removed,
        "anomaly_count": anomaly_count,
        "rows_before_dedupe": rows_before_dedupe,
        "mapped_columns": mapping,
        "mapping_scores": mapping_scores,
        "mapping_cache_hit": cache_hit,
        "standard_columns": list(STANDARD_COLUMNS),
        "failed_required_columns": unresolved_required,
    }
    return {"clean_df": flagged, "report": report}
