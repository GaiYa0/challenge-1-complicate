"""
Kafka 消费者进程：订阅业务 topics，失败重试后写入 DLQ。

运行（项目根目录）：

    export PYTHONPATH=.
    python -m backend.events.kafka_consumer
"""

from __future__ import annotations

import json
import logging
import signal
import sys

from kafka import KafkaConsumer
from kafka.errors import KafkaError

from backend.core.config import get_settings
from backend.events.dlq import send_to_dlq
from backend.events.handlers import dispatch_with_retries
from backend.events.topics import (
    DATA_PROCESSED,
    DATA_UPLOADED,
    MODEL_TRAINED,
    PREDICTION_DONE,
)

_log = logging.getLogger("kafka.consumer")

_stop = False


def _sig(_sig, _frame):
    global _stop
    _stop = True


def run_forever() -> None:
    s = get_settings()
    if not s.KAFKA_ENABLED:
        _log.error("KAFKA_ENABLED=false，退出。请设置 KAFKA_ENABLED=true 与 KAFKA_BOOTSTRAP_SERVERS。")
        sys.exit(1)

    topics = (DATA_UPLOADED, DATA_PROCESSED, MODEL_TRAINED, PREDICTION_DONE)
    consumer = KafkaConsumer(
        *topics,
        bootstrap_servers=s.KAFKA_BOOTSTRAP_SERVERS.split(","),
        group_id=s.KAFKA_CONSUMER_GROUP,
        enable_auto_commit=False,
        consumer_timeout_ms=1000,
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
        key_deserializer=lambda b: b.decode("utf-8") if b else None,
    )
    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)
    _log.info("consumer started topics=%s group=%s", topics, s.KAFKA_CONSUMER_GROUP)

    try:
        while not _stop:
            try:
                batch = consumer.poll(timeout_ms=2000)
            except KafkaError:
                _log.exception("poll failed")
                continue
            for tp, records in batch.items():
                for msg in records:
                    try:
                        dispatch_with_retries(msg.topic, msg.value)
                        consumer.commit()
                    except Exception as e:
                        _log.exception("message failed after retries topic=%s", msg.topic)
                        send_to_dlq(
                            original_topic=msg.topic,
                            payload=msg.value if isinstance(msg.value, dict) else {},
                            error=str(e),
                            partition=msg.partition,
                            offset=msg.offset,
                        )
                        consumer.commit()
    finally:
        consumer.close()
        _log.info("consumer stopped")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    run_forever()


if __name__ == "__main__":
    main()
