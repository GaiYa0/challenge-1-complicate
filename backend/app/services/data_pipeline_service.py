"""
标准化数据处理流水线（供 Celery Worker 与后续数据湖扩展复用）。

步骤：MinIO 读入 → 清洗（空值、类型、异常扫描）→ 特征摘要 → 下游持久化由具体任务完成。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import numpy as np
import pandas as pd
from minio import Minio
from sqlalchemy.orm import Session

from backend.infra import minio_client as minio_ops
from backend.app.repositories import field_mapping_repo, file_repo
from backend.core.config import get_settings
from backend.core.exceptions import ServiceError
from backend.app.services.file_service import read_tabular_bytes_to_dataframe
from backend.data_platform.normalization_engine import (
    clean_and_standardize,
    invalidate_mapping_cache,
)
from backend.utils.analyze_utils import feature_dict_from_dataframe

logger = logging.getLogger(__name__)


def _header_signature(columns: list[object]) -> str:
    normalized = []
    for c in columns:
        s = str(c or "").strip().lower()
        s = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", s)
        if s:
            normalized.append(s)
    normalized = sorted(set(normalized))
    return "|".join(normalized)


def read_user_csv_dataframe(
    db: Session,
    minio: Minio,
    *,
    filename: str,
    user_id: int,
) -> pd.DataFrame:
    """1) 从 MinIO 按元数据表读取用户可见结构化文件。"""
    row = file_repo.get_file_for_tenant(db, filename, user_id)
    if row is None:
        raise ServiceError("file not found")
    raw = minio_ops.get_bytes(minio, row.bucket_name, row.object_name)
    return read_tabular_bytes_to_dataframe(filename, raw)


def standard_clean(
    db: Session,
    df: pd.DataFrame,
    *,
    user_id: int,
    filename: str,
    persist_mapping: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    2) 清洗：去全空行、尽量数值化、记录行数变化。
    """
    rows_before = int(len(df))
    df2 = df.dropna(how="all").copy()
    normalized_report: dict[str, Any] = {}
    settings = get_settings()
    signature = _header_signature(list(df2.columns))
    learned_mapping, reuse_score = field_mapping_repo.find_best_mapping(
        db,
        user_id=user_id,
        header_signature=signature,
        min_similarity=float(settings.IMPORT_MAPPING_REUSE_MIN_SIMILARITY),
        touch_usage=persist_mapping,
    )
    try:
        result = clean_and_standardize(
            df2,
            learned_mapping=learned_mapping,
            mapping_cache_key=f"{user_id}:{filename}:{signature}",
            name_weight=float(settings.IMPORT_MATCH_NAME_WEIGHT),
            content_weight=float(settings.IMPORT_MATCH_CONTENT_WEIGHT),
            min_match_score=float(settings.IMPORT_MATCH_MIN_SCORE),
        )
        clean_df = result.get("clean_df")
        if isinstance(clean_df, pd.DataFrame):
            df2 = clean_df
        normalized_report = dict(result.get("report") or {})
        mapped_columns = dict(normalized_report.get("mapped_columns") or {})
        mapping_scores = {
            str(k): float((v or {}).get("final", 0.0))
            for k, v in dict(normalized_report.get("mapping_scores") or {}).items()
        }
        if persist_mapping:
            field_mapping_repo.upsert_mapping(
                db,
                user_id=user_id,
                header_signature=signature,
                mapping=mapped_columns,
                confidence_by_source=mapping_scores,
            )
        normalized_report["mapping_reuse_score"] = reuse_score
    except Exception:
        normalized_report = {}
    for col in df2.columns:
        if df2[col].dtype == object:
            converted = pd.to_numeric(df2[col], errors="coerce")
            if converted.notna().sum() >= max(1, int(0.5 * len(df2))):
                df2[col] = converted
    rows_after = int(len(df2))
    meta = {
        "rows_before": rows_before,
        "rows_after": rows_after,
        "columns": [str(c) for c in df2.columns],
        "normalization": normalized_report,
    }
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
    df_raw = read_user_csv_dataframe(db, minio, filename=filename, user_id=user_id)
    df_clean, clean_meta = standard_clean(db, df_raw, user_id=user_id, filename=filename)
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


def confirm_field_mapping(
    db: Session,
    minio: Minio,
    *,
    filename: str,
    user_id: int,
    mapping: dict[str, str],
) -> dict[str, Any]:
    df = read_user_csv_dataframe(db, minio, filename=filename, user_id=user_id)
    signature = _header_signature(list(df.columns))
    field_mapping_repo.upsert_mapping(
        db,
        user_id=user_id,
        header_signature=signature,
        mapping={str(k): str(v) for k, v in (mapping or {}).items()},
        confidence_by_source={str(k): 100.0 for k in (mapping or {})},
    )
    # 手动确认后优先保证“同用户下所有同结构表”立即生效，避免跨文件命中旧缓存。
    invalidate_mapping_cache(prefix=f"{user_id}:")
    return {
        "learned": True,
        "header_signature": signature,
        "mapping_size": len(mapping or {}),
    }
