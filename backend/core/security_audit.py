"""
安全审计日志：登录失败、权限拒绝、异常访问（结构化 JSON，logger=security.audit）。
"""

from __future__ import annotations

import json
import logging
from typing import Any

_audit = logging.getLogger("security.audit")


def log_security_event(event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    _audit.warning("%s", json.dumps(payload, ensure_ascii=False, default=str))
