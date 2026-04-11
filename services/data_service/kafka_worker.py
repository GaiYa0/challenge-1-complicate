"""
data-service Kafka 消费示例：处理异步数据流水线事件，从 headers 解析 request_id 并写入结构化日志。

运行（项目根，PYTHONPATH=.）：

  KAFKA_BOOTSTRAP_SERVERS=localhost:19092 python -m services.data_service.kafka_worker
"""

from __future__ import annotations

import json
import logging
import os
import sys

from services.common.kafka_topics import MS_DATA_PIPELINE
from services.common.logging_setup import configure_logging

_log = logging.getLogger("data.kafka.consumer")


def main() -> None:
    configure_logging("data-service")
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")
    group = os.getenv("KAFKA_GROUP_ID", "data-service-governance-demo")

    from kafka import KafkaConsumer

    def _safe_deserialize(b: bytes) -> dict | None:
        try:
            return json.loads(b.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            _log.warning("bad_message_skipped raw=%s", b[:200])
            return None

    consumer = KafkaConsumer(
        MS_DATA_PIPELINE,
        bootstrap_servers=bootstrap.split(","),
        group_id=group,
        enable_auto_commit=True,
        auto_offset_reset="earliest",
        value_deserializer=_safe_deserialize,
    )
    _log.info("consumer_started topic=%s group=%s", MS_DATA_PIPELINE, group)
    try:
        for msg in consumer:
            if msg.value is None:
                continue
            rid = None
            if msg.headers:
                for hk, hv in msg.headers:
                    if hk == "request_id":
                        rid = hv.decode("utf-8") if isinstance(hv, (bytes, bytearray)) else str(hv)
            _log.info(
                "event_received request_id=%s partition=%s offset=%s value=%s",
                rid,
                msg.partition,
                msg.offset,
                msg.value,
            )
    except KeyboardInterrupt:
        _log.info("consumer_stopped")
    finally:
        consumer.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        _log.exception("consumer_failed")
        sys.exit(1)
