"""
事件处理器：topic → 业务动作（内部可同步等待 Celery 结果以保证顺序与重试语义）。
"""

from __future__ import annotations

import logging
import time

from backend.core.config import get_settings
from backend.events.schemas import EventEnvelope, parse_envelope
from backend.events.topics import DATA_PROCESSED, DATA_UPLOADED, MODEL_TRAINED, PREDICTION_DONE
from backend.app.services import ml_model_service
from backend.tasks import runtime
from backend.tasks.celery_app import celery_app
from backend.tasks.clean_task import clean_data_task
from backend.tasks.feature_task import feature_extract_task

_log = logging.getLogger("kafka.handlers")


def handle_data_uploaded(ev: EventEnvelope) -> None:
    """data-uploaded → 清洗（Celery fire-and-forget + chain）。"""
    _log.info("handle data-uploaded user=%s file=%s", ev.user_id, ev.resource_id)
    clean_data_task.apply_async(
        args=(ev.resource_id, ev.user_id),
        link=feature_extract_task.s(ev.user_id),
    )


def handle_data_processed(ev: EventEnvelope) -> None:
    """data-processed → 特征生成（非阻塞）。"""
    _log.info("handle data-processed user=%s file=%s", ev.user_id, ev.resource_id)
    feature_extract_task.delay(ev.resource_id, ev.user_id)


def handle_model_trained(ev: EventEnvelope) -> None:
    """model-trained → 可选自动激活 Model Registry。"""
    _log.info("handle model-trained user=%s ref=%s", ev.user_id, ev.resource_id)
    s = get_settings()
    if not s.KAFKA_AUTO_ACTIVATE_MODEL:
        return
    parts = ev.resource_id.split("|", 1)
    if len(parts) != 2:
        raise ValueError("model-trained resource_id must be model_name|version")
    model_name, version = parts[0].strip(), parts[1].strip()
    db = runtime.open_session()
    try:
        ml_model_service.activate_version(db, model_name=model_name, version=version)
    finally:
        db.close()


def handle_prediction_done(ev: EventEnvelope) -> None:
    """prediction-done：审计 / 下游可订阅扩展。"""
    _log.info("prediction-done user=%s resource=%s", ev.user_id, ev.resource_id)


def dispatch(topic: str, raw: dict) -> None:
    ev = parse_envelope(raw)
    if topic == DATA_UPLOADED:
        handle_data_uploaded(ev)
    elif topic == DATA_PROCESSED:
        handle_data_processed(ev)
    elif topic == MODEL_TRAINED:
        handle_model_trained(ev)
    elif topic == PREDICTION_DONE:
        handle_prediction_done(ev)
    else:
        raise ValueError(f"unknown topic: {topic}")


def dispatch_with_retries(topic: str, raw: dict) -> None:
    s = get_settings()
    max_r = max(1, int(s.KAFKA_CONSUMER_MAX_RETRIES))
    base = float(s.KAFKA_CONSUMER_RETRY_BASE_SEC)
    last: Exception | None = None
    for attempt in range(max_r):
        try:
            dispatch(topic, raw)
            return
        except Exception as e:
            last = e
            _log.warning(
                "handler failed topic=%s attempt=%s/%s err=%s",
                topic,
                attempt + 1,
                max_r,
                e,
                exc_info=s.DEBUG,
            )
            if attempt < max_r - 1:
                time.sleep(base * (2**attempt))
    if last:
        raise last
