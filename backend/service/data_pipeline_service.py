"""
标准化数据处理流水线（供 Celery Worker 与后续数据湖扩展复用）。

步骤：MinIO 读入 → 清洗（空值、类型、异常扫描）→ 特征摘要 → 下游持久化由具体任务完成。
"""

from __future__ import annotations

import json
import logging
from io import BytesIO
from typing import Any

import numpy as np
import pandas as pd
from minio import Minio
from sqlalchemy.orm import Session

from backend.infra import minio_client as minio_ops
from backend.repository import file_repo
from backend.utils.analyze_utils import feature_dict_from_dataframe

logger = logging.getLogger(__name__)


def read_user_csv_dataframe(
    db: Session,
    minio: Minio,
    *,
    filename: str,
    user_id: int,
) -> pd.DataFrame:
    """1) 从 MinIO 按元数据表读取用户可见 CSV。"""
    row = file_repo.get_file_for_tenant(db, filename, user_id)
    if row is None:
        raise ValueError("file not found")
    raw = minio_ops.get_bytes(minio, row.bucket_name, row.object_name)
    return pd.read_csv(BytesIO(raw))


def standard_clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    2) 清洗：去全空行、尽量数值化、记录行数变化。
    """
    rows_before = int(len(df))
    df2 = df.dropna(how="all").copy()
    for col in df2.columns:
        if df2[col].dtype == object:
            converted = pd.to_numeric(df2[col], errors="coerce")
            if converted.notna().sum() >= max(1, int(0.5 * len(df2))):
                df2[col] = converted
    rows_after = int(len(df2))
    meta = {"rows_before": rows_before, "rows_after": rows_after, "columns": [str(c) for c in df2.columns]}
    logger.info("pipeline_clean: %s", json.dumps(meta, ensure_ascii=False))
    return df2, meta


def anomaly_scan_numeric(df: pd.DataFrame) -> dict[str, Any]:
    """2c) 简易数值异常检测（2σ 外计数，按列汇总）。"""
    num_df = df.select_dtypes(include=[np.integer, np.floating])
    per_col: dict[str, int] = {}
    total = 0
    for col in num_df.columns:
        s = num_df[col].dropna()
        if len(s) == 0:
            per_col[str(col)] = 0
            continue
        m, st = float(s.mean()), float(s.std())
        if st == 0 or np.isnan(st):
            per_col[str(col)] = 0
            continue
        bad = s.notna() & ((s < m - 2 * st) | (s > m + 2 * st))
        c = int(bad.sum())
        per_col[str(col)] = c
        total += c
    return {"per_column": per_col, "total_flags": total}


def extract_feature_dict(df: pd.DataFrame) -> dict[str, object]:
    """3) 特征摘要（数值列统计）。"""
    return feature_dict_from_dataframe(df)


def run_pipeline_dataframe(
    db: Session,
    minio: Minio,
    *,
    filename: str,
    user_id: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """读入 → 清洗 → 异常扫描 → 特征；返回 (清洗后 DataFrame, 可 JSON 摘要)。"""
    if not str(filename).lower().endswith(".csv"):
        raise ValueError("only csv allowed")
    df_raw = read_user_csv_dataframe(db, minio, filename=filename, user_id=user_id)
    df_clean, clean_meta = standard_clean(df_raw)
    anomalies = anomaly_scan_numeric(df_clean)
    features = extract_feature_dict(df_clean)
    summary = {
        "filename": filename,
        "clean": clean_meta,
        "anomalies": anomalies,
        "features": features,
    }
    return df_clean, summary


def run_standard_pipeline(
    db: Session,
    minio: Minio,
    *,
    filename: str,
    user_id: int,
) -> dict[str, Any]:
    """仅返回可 JSON 序列化的摘要。"""
    _, summary = run_pipeline_dataframe(db, minio, filename=filename, user_id=user_id)
    return summary
