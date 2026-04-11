"""
流处理扩展（任务3）：与 Kafka 管线衔接的实时钩子。

在线推理路径仍以 Kafka 事件为主；此处提供：
- 特征上线后的轻量通知 / 风险占位（可接 Flink/Kafka Streams）
"""

from __future__ import annotations

import logging
import math
from typing import Any

_log = logging.getLogger("data_platform.streaming")


def notify_feature_online(*, user_id: int, entity_id: int, version: str) -> None:
    """特征版本写入 Redis 后调用：可扩展为向 Kafka 发 feature-updated 供实时服务消费。"""
    _log.info("stream_hook feature_online uid=%s entity=%s ver=%s", user_id, entity_id, version)


def eval_streaming_risk(feature_row: dict[str, Any]) -> str:
    """
    可选实时风险：基于数值特征简单规则（演示）。
    生产可改为模型分或规则引擎结果写入 Kafka / 告警系统。
    """
    nums = [v for v in feature_row.values() if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not nums:
        return "low"
    s = sum(abs(float(x)) for x in nums)
    if math.isnan(s):
        return "medium"
    if s > 1e6:
        return "high"
    if s > 1e3:
        return "medium"
    return "low"
