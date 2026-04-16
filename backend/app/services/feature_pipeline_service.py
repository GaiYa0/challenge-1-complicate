"""
特征生成标准化流水线：从 MinIO 读入 clean（或 raw→清洗）→ 统计 / 行为 / 时间特征 → dict（带 version 由上层写入）。
"""

from __future__ import annotations

from io import BytesIO
from typing import Any

import numpy as np
import pandas as pd
from minio import Minio
from sqlalchemy.orm import Session

from backend.infra import minio_client as minio_ops
from backend.model.enums import DataLayer
from backend.model.models import File
from backend.app.repositories import file_repo
from backend.app.services.data_pipeline_service import read_user_csv_dataframe, standard_clean
from backend.utils.analyze_utils import feature_dict_from_dataframe


def read_clean_dataframe(
    db: Session,
    minio: Minio,
    *,
    user_id: int,
    entity_id: int,
) -> tuple[pd.DataFrame, File]:
    """
    1) 优先读对象本身为 clean 分层的数据；
    2) 否则从 MinIO 读 raw CSV，在内存中走与数据湖一致的 standard_clean。
    """
    row = file_repo.get_file_by_id_for_tenant(db, entity_id, user_id)
    if row is None:
        raise ValueError("entity not found")

    if row.data_layer == DataLayer.CLEAN.value:
        raw = minio_ops.get_bytes(minio, row.bucket_name, row.object_name)
        return pd.read_csv(BytesIO(raw)), row

    df_raw = read_user_csv_dataframe(db, minio, filename=row.filename, user_id=user_id)
    df_clean, _ = standard_clean(df_raw)
    return df_clean, row


def extract_standard_features(df: pd.DataFrame, file_row: File) -> dict[str, Any]:
    """
    统计特征：均值、标准差、方差；
    行为特征：空值率、列类型比例等；
    时间特征：实体创建时刻 + 数据中日期列范围。
    """
    out: dict[str, Any] = dict(feature_dict_from_dataframe(df))

    num_df = df.select_dtypes(include=[np.integer, np.floating])
    for col in num_df.columns:
        base = str(col)
        s = num_df[col]
        var = s.var()
        out[f"{base}_var"] = None if pd.isna(var) else float(var)

    nrows, ncols = len(df), max(len(df.columns), 1)
    out["behavior_null_rate_mean"] = float(df.isna().mean().mean()) if nrows else 0.0
    out["behavior_numeric_col_ratio"] = float(len(num_df.columns) / ncols)
    out["behavior_row_to_col_ratio"] = float(nrows / ncols)

    ca = getattr(file_row, "created_at", None)
    if ca is not None:
        out["time_entity_created_hour_utc"] = int(ca.hour)
        out["time_entity_created_dow"] = int(ca.weekday())

    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            s = pd.to_datetime(df[col], errors="coerce")
            if s.notna().any():
                mn, mx = s.min(), s.max()
                out[f"time_{col}_min"] = mn.isoformat() if pd.notna(mn) else None
                out[f"time_{col}_max"] = mx.isoformat() if pd.notna(mx) else None

    return out
