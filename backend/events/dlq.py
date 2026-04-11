"""
死信队列：消费失败且超过重试后写入 events-dlq（保留原 topic 与错误信息）。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from kafka import KafkaProducer
from kafka.errors import KafkaError

from backend.core.config import get_settings
from backend.events.topics import EVENTS_DLQ

_log = logging.getLogger("kafka.dlq")

_dlq_producer: KafkaProducer | None = None


def _dlq() -> KafkaProducer | None:
    global _dlq_producer
    s = get_settings()
    if not s.KAFKA_ENABLED:
        return None
    if _dlq_producer is not None:
        return _dlq_producer
    try:
        _dlq_producer = KafkaProducer(
            bootstrap_servers=s.KAFKA_BOOTSTRAP_SERVERS.split(","),
            client_id=f"{s.KAFKA_CLIENT_ID}-dlq",
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
            acks="all",
            retries=2,
        )
        return _dlq_producer
    except Exception:
        _log.exception("dlq producer init failed")
        return None


def send_to_dlq(
    *,
    original_topic: str,
    payload: dict[str, Any],
    error: str,
    partition: int | None = None,
    offset: int | None = None,
) -> None:
    p = _dlq()
    body = {
        "original_topic": original_topic,
        "original_partition": partition,
        "original_offset": offset,
        "error": error[:4000],
        "payload": payload,
    }
    if p is None:
        _log.critical(
            "dlq_message_lost: producer unavailable original_topic=%s error=%s payload=%s",
            original_topic, error, json.dumps(payload, default=str)[:2000],
        )
        return
    try:
        p.send(EVENTS_DLQ, value=body).get(timeout=10)
    except KafkaError:
        _log.critical(
            "dlq_send_failed: message may be lost original_topic=%s error=%s",
            original_topic, error, exc_info=True,
        )
