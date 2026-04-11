import json
import logging
from typing import Any

_log = logging.getLogger("user_service.audit")


def log_event(event: str, **fields: Any) -> None:
    _log.warning("%s", json.dumps({"event": event, **fields}, ensure_ascii=False, default=str))
