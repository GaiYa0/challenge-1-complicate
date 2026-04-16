"""
计算分级：小任务同步、大任务 Celery、超大任务预留 Spark。

注意：具体阈值应结合机器规格与 SLA 调参；此处给出可运行的保守默认值。
"""

from __future__ import annotations

# 同步处理上限（字节）：小预览 / 小 CSV
SYNC_COMPUTE_MAX_BYTES = 512 * 1024
# Celery 上限（字节）：以下仍走 worker，超过则标记 spark
CELERY_COMPUTE_MAX_BYTES = 8 * 1024 * 1024


def route_compute_tier(estimated_bytes: int | None) -> str:
    if estimated_bytes is None or estimated_bytes <= 0:
        return "sync"
    if estimated_bytes <= SYNC_COMPUTE_MAX_BYTES:
        return "sync"
    if estimated_bytes <= CELERY_COMPUTE_MAX_BYTES:
        return "celery"
    return "spark"
