"""
数据湖路径规范（MinIO 对象键前缀）

逻辑布局（单桶或多桶均可；当前实现：raw 在 raw-data，clean/feature 在 processed-data）：

- raw/{user_id}/{dataset}/{version}/{filename}     — 原始层，只追加、不覆盖业务语义
- clean/{user_id}/{dataset}/{version}/{filename}   — 清洗层
- feature/{user_id}/{dataset}/{version}/{filename} — 特征快照（Parquet/JSON 等）

与 minio_client.bucket_for_layer 组合使用：bucket 按物理分层，key 按上述逻辑分层。
"""

from __future__ import annotations


def _segment(value: str, *, max_len: int = 256) -> str:
    s = (value or "default").strip().replace("..", "").replace("\\", "/").strip("/")
    return (s or "default")[:max_len]


def lake_directory_prefix(layer: str, user_id: int, dataset: str) -> str:
    """目录语义前缀（以 / 结尾），用于列举或文档。"""
    ly = _segment(layer, max_len=16).lower()
    if ly not in ("raw", "clean", "feature"):
        ly = "raw"
    return f"{ly}/{int(user_id)}/{_segment(dataset)}/"


def lake_object_key(layer: str, user_id: int, dataset: str, version: str, filename: str) -> str:
    """对象完整 key：{layer}/{user_id}/{dataset}/{version}/{filename}"""
    ly = _segment(layer, max_len=16).lower()
    if ly not in ("raw", "clean", "feature"):
        ly = "raw"
    return (
        f"{ly}/{int(user_id)}/{_segment(dataset)}/"
        f"{_segment(version, max_len=64)}/{_segment(filename, max_len=512)}"
    )
