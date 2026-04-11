from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any

from services.common.tracing import get_request_id


class JsonLogFormatter(logging.Formatter):
    """面向 ELK 的 JSON 单行日志：字段稳定便于 Filebeat/Logstash 解析。"""

    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "@timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service_name,
            "request_id": getattr(record, "request_id", None) or get_request_id(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)
        return json.dumps(payload, ensure_ascii=False)


class RequestIdLogFilter(logging.Filter):
    """把 contextvar 中的 request_id 注入到每条 LogRecord。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "request_id", None):
            record.request_id = get_request_id()
        return True


def configure_logging(service_name: str, level: str = "INFO") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter(service_name=service_name))
    handler.addFilter(RequestIdLogFilter())
    root.addHandler(handler)
    root.setLevel(level)
