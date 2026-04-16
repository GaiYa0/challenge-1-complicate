"""
Aggregated application package.

历史上后端按顶层 `backend.core`、`backend.middleware`、`backend.infra`、
`backend.events`、`backend.tasks`、`backend.model` 等模块分层；本次把它们
**逻辑并入** `backend.app.*` —— 通过 `sys.modules` 注册别名，让旧路径
与新路径（`backend.app.core.*` / `backend.app.tasks.*` …）完全等价。

这样既避免机械地搬动上百个 import，也让后续代码可以只使用 `backend.app.*`
命名空间，达到与 `routers/services/repositories/schemas` 一致的聚合结构。
"""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

_ALIASED: tuple[str, ...] = (
    "core",
    "middleware",
    "infra",
    "events",
    "tasks",
    "model",
    "data_platform",
    "utils",
    "contracts",
)

for _name in _ALIASED:
    try:
        _mod = _import_module(f"backend.{_name}")
    except Exception:  # pragma: no cover - 某些子包可选
        continue
    _alias = f"{__name__}.{_name}"
    _sys.modules.setdefault(_alias, _mod)
    globals()[_name] = _mod
