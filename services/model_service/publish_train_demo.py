"""
model-service：异步触发训练任务（Kafka）示例脚本。

  export KAFKA_BOOTSTRAP_SERVERS=localhost:19092
  PYTHONPATH=. python -m services.model_service.publish_train_demo
"""

from __future__ import annotations

import os

from services.common.kafka_bus import close_producer, publish_event
from services.common.kafka_topics import MS_MODEL_TRAIN
from services.common.logging_setup import configure_logging


def main() -> None:
    configure_logging("model-service")
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")
    publish_event(
        bootstrap_servers=bootstrap,
        topic=MS_MODEL_TRAIN,
        payload={"type": "model_train", "model_name": "demo", "version": "1"},
        key="demo",
    )


if __name__ == "__main__":
    try:
        main()
    finally:
        close_producer()
