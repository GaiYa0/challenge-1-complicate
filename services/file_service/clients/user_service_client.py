"""
file-service 通过 HTTP 调用 user-service，禁止直连 user_db。

环境变量示例：
  USER_SERVICE_URL=http://localhost:8001
  INTERNAL_API_TOKEN=与 user-service 的 INTERNAL_API_TOKEN 一致
"""

from __future__ import annotations

import os
from typing import Any

from services.common.http_resilient import sync_request_with_retry


class UserServiceClient:
    def __init__(
        self,
        base_url: str | None = None,
        internal_token: str | None = None,
        timeout_s: float = 5.0,
    ):
        self._base = (base_url or os.getenv("USER_SERVICE_URL", "http://localhost:8001")).rstrip("/")
        self._token = internal_token or os.getenv("INTERNAL_API_TOKEN", "")
        self._timeout = timeout_s

    def _headers(self) -> dict[str, str]:
        return {"X-Internal-Token": self._token}

    def get_user(self, user_id: int) -> dict[str, Any]:
        r = sync_request_with_retry(
            "GET",
            f"{self._base}/internal/v1/users/{user_id}",
            timeout_s=self._timeout,
            headers=self._headers(),
            max_attempts=3,
        )
        r.raise_for_status()
        return r.json()

    def validate_token(self, token: str) -> dict[str, Any]:
        r = sync_request_with_retry(
            "POST",
            f"{self._base}/internal/v1/token/validate",
            timeout_s=self._timeout,
            headers=self._headers(),
            json_body={"token": token},
            max_attempts=3,
        )
        r.raise_for_status()
        return r.json()
