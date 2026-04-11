from __future__ import annotations

import time
from dataclasses import dataclass


class CircuitOpenError(Exception):
    """熔断打开：停止调用下游，由调用方返回降级结果。"""


@dataclass
class CircuitState:
    failures: int = 0
    opened_until: float | None = None


class AsyncCircuitBreaker:
    """极简异步熔断：连续失败达到阈值后在一段时间内直接拒绝。"""

    def __init__(self, *, fail_max: int = 5, reset_timeout_s: float = 30.0):
        self.fail_max = fail_max
        self.reset_timeout_s = reset_timeout_s
        self._state = CircuitState()

    def _is_open(self) -> bool:
        if self._state.opened_until is None:
            return False
        if time.monotonic() < self._state.opened_until:
            return True
        # 半开：允许一次试探
        self._state.opened_until = None
        self._state.failures = 0
        return False

    async def call(self, fn):
        if self._is_open():
            raise CircuitOpenError("circuit open")

        try:
            result = await fn()
            self._state.failures = 0
            return result
        except Exception:
            self._state.failures += 1
            if self._state.failures >= self.fail_max:
                self._state.opened_until = time.monotonic() + self.reset_timeout_s
            raise
