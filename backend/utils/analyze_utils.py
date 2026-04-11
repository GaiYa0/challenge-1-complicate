from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd


def feature_dict_from_dataframe(df: pd.DataFrame) -> dict[str, object]:
    """从 DataFrame 提取特征（与 CSV 字节版逻辑一致）。"""
    num_df = df.select_dtypes(include=[np.integer, np.floating])
    features_payload: dict[str, object] = {"row_count": int(len(df))}
    for col in num_df.columns:
        base = str(col)
        s = num_df[col]
        m, st = s.mean(), s.std()
        features_payload[f"{base}_mean"] = None if pd.isna(m) else float(m)
        features_payload[f"{base}_std"] = None if pd.isna(st) else float(st)
    return features_payload


def feature_dict_from_csv_bytes(raw: bytes) -> dict[str, object]:
    """从 CSV 字节提取特征（MinIO / 对象存储）。"""
    df = pd.read_csv(BytesIO(raw))
    return feature_dict_from_dataframe(df)


def feature_dict_from_csv_path(target: Path) -> dict[str, object]:
    """数值列 mean/std + row_count（本地路径，遗留/工具脚本）。"""
    df = pd.read_csv(target)
    return feature_dict_from_dataframe(df)


def analyze_risk_level(score: float) -> str:
    """统一规则：≤30 low，31–70 medium，>70 high。"""
    if score <= 30:
        return "low"
    if score <= 70:
        return "medium"
    return "high"


def analyze_cache_key(kind: str, user_id: int, filename: str) -> str:
    """与 infra.redis_client.analyze_cache_key 一致（Celery / 工具复用）。"""
    from backend.infra.redis_client import analyze_cache_key as _key

    return _key(kind, user_id, filename)
