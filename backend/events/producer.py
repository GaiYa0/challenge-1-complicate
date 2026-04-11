"""
Kafka Producer：懒连接、与业务解耦；关闭 KAFKA_ENABLED 时不发送。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from kafka import KafkaProducer
from kafka.errors import KafkaError

from backend.core.config import get_settings
from backend.events.schemas import build_envelope
from backend.events.topics import (
    DATA_PROCESSED,
    DATA_UPLOADED,
    MODEL_TRAINED,
    PREDICTION_DONE,
)

_log = logging.getLogger("kafka.producer")

_producer: KafkaProducer | None = None


def _get_producer() -> KafkaProducer | None:
    global _producer
    settings = get_settings()
    if not settings.KAFKA_ENABLED:
        return None
    if _producer is not None:
        return _producer
    try:
        _producer = KafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
            client_id=settings.KAFKA_CLIENT_ID,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k is not None else None,
            acks="all",
            retries=3,
        )
        return _producer
    except Exception:
        _log.exception("kafka producer init failed")
        return None


def publish(topic: str, *, event_type: str, user_id: int, resource_id: str) -> None:
    body = build_envelope(event_type=event_type, user_id=user_id, resource_id=resource_id)
    p = _get_producer()
    if p is None:
        return
    try:
        fut = p.send(topic, key=str(user_id), value=body)
        fut.get(timeout=15)
    except KafkaError:
        _log.exception("kafka publish failed topic=%s", topic)


def publish_data_uploaded(user_id: int, logical_filename: str) -> None:
    publish(DATA_UPLOADED, event_type="data-uploaded", user_id=user_id, resource_id=logical_filename)


def publish_data_processed(user_id: int, resource_id: str) -> None:
    publish(DATA_PROCESSED, event_type="data-processed", user_id=user_id, resource_id=resource_id)


def publish_model_trained(user_id: int, model_name: str, model_version: str) -> None:
    rid = f"{model_name}|{model_version}"
    publish(MODEL_TRAINED, event_type="model-trained", user_id=user_id, resource_id=rid)


def publish_prediction_done(user_id: int, filename: str) -> None:
    publish(PREDICTION_DONE, event_type="prediction-done", user_id=user_id, resource_id=filename)


def flush_producer() -> None:
    if _producer is not None:
        try:
            _producer.flush(timeout=5)
        except Exception:
            _log.warning("kafka flush failed", exc_info=True)


def close_producer() -> None:
    global _producer
    if _producer is not None:
        try:
            _producer.close()
        finally:
            _producer = None
