"""
Kafka 异步事件：在消息 headers 中携带 request_id，便于消费端与日志对齐。

本地 Redpanda：docker compose -f docker-compose.kafka.yml up -d
环境变量：KAFKA_ENABLED=true KAFKA_BOOTSTRAP_SERVERS=localhost:19092
"""

from __future__ import annotations

import json
import logging
from typing import Any

from services.common.tracing import get_request_id

_log = logging.getLogger("kafka.bus")

_producer = None


def _producer_cls():
    from kafka import KafkaProducer

    return KafkaProducer


def get_producer(bootstrap_servers: str, client_id: str = "ms-governance"):
    global _producer
    if _producer is not None:
        return _producer
    KafkaProducer = _producer_cls()
    _producer = KafkaProducer(
        bootstrap_servers=bootstrap_servers.split(","),
        client_id=client_id,
        value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k is not None else None,
        acks="all",
        retries=3,
        request_timeout_ms=15000,
    )
    return _producer


def publish_event(
    *,
    bootstrap_servers: str,
    topic: str,
    payload: dict[str, Any],
    key: str | None = None,
) -> None:
    rid = get_request_id()
    headers: list[tuple[str, bytes]] = []
    if rid:
        headers.append(("request_id", rid.encode("utf-8")))
    p = get_producer(bootstrap_servers)
    try:
        fut = p.send(topic, key=key, value=payload, headers=headers or None)
        fut.get(timeout=15)
        _log.info("kafka_published topic=%s request_id=%s", topic, rid)
    except Exception:
        _log.exception("kafka_publish_failed topic=%s", topic)
        raise


def close_producer() -> None:
    global _producer
    if _producer is not None:
        try:
            _producer.flush()
            _producer.close()
        finally:
            _producer = None
