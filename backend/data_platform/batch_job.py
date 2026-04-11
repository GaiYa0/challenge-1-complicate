"""
批处理（任务2）：大规模清洗 / 特征计算。

生产环境可替换为 Spark；此处提供与数据湖路径一致的 **Pandas 模拟批**，
便于在无 Spark 集群时跑通「历史分区 → clean/feature」链路。
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from minio import Minio

from backend.infra import minio_client as mc


# --- Spark 作业骨架（伪代码，供集群侧实现） ------------------------------------
_SPARK_BATCH_DOC = '''
# PySpark 示例（生产集群）
#
# from pyspark.sql import SparkSession
# spark = SparkSession.builder.appName("lake-batch-clean").getOrCreate()
# raw_df = spark.read.format("csv").load("s3a://raw-data/raw/{user_id}/{dataset}/**")
# cleaned = raw_df.na.drop(how="all").fillna(0)  # 业务规则扩展
# cleaned.write.mode("overwrite").parquet(
#     "s3a://processed-data/clean/{user_id}/{dataset}/dt=2026-01-01/"
# )
# feat = cleaned.groupBy("entity").agg({"amount": "avg", "amount": "var_pop"})
# feat.write.mode("overwrite").parquet(
#     "s3a://processed-data/feature/{user_id}/{dataset}/dt=2026-01-01/"
# )
#
# 批输出与流式增量最终都写入同一 Feature Store（PG + Redis），实现流批一体。
'''


def spark_batch_pseudocode() -> str:
    """返回 Spark 批作业说明字符串（文档/日志）。"""
    return _SPARK_BATCH_DOC.strip()


def run_pandas_batch_clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """模拟批清洗：去全空行 + 数值列推断（与在线清洗规则可对齐）。"""
    before = int(len(df))
    out = df.dropna(how="all").copy()
    for col in out.columns:
        if out[col].dtype == object:
            converted = pd.to_numeric(out[col], errors="coerce")
            if converted.notna().sum() >= max(1, int(0.5 * len(out))):
                out[col] = converted
    meta = {"rows_before": before, "rows_after": int(len(out)), "columns": [str(c) for c in out.columns]}
    return out, meta


def export_feature_snapshot_to_lake(
    client: Minio,
    *,
    user_id: int,
    dataset: str,
    version: str,
    logical_name: str,
    feature_dict: dict[str, Any],
) -> str:
    """
    将特征快照写入 MinIO feature 层（JSON），路径符合数据湖规范。
    注意：权威 Feature Store 仍为 PG+Redis；本对象为批/审计副本。
    """
    key = mc.build_object_name(user_id, dataset, version, logical_name, layer="feature")
    bucket = mc.bucket_for_layer("feature")
    body = json.dumps(feature_dict, ensure_ascii=False, default=str).encode("utf-8")
    mc.put_bytes(client, bucket, key, body, content_type="application/json")
    return key
