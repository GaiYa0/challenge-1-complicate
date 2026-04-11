"""
已废弃：请改用 ``from backend.core.exceptions import ...``。
本模块仅为向后兼容保留，将在后续版本移除。
"""

import warnings as _warnings

_warnings.warn(
    "backend.core.exception is deprecated, use backend.core.exceptions instead",
    DeprecationWarning,
    stacklevel=2,
)

from backend.core.exceptions import (  # noqa: F401, E402
    AppError,
    AuthError,
    ForbiddenError,
    ParamError,
    RateLimitError,
    ServiceError,
    SystemError,
)
