"""
应用异常：业务/参数/认证/权限/系统。
Service 与各层抛出 → main 全局处理器 → 统一响应体（含 request_id）。
"""


class AppError(Exception):
    """基类：携带 HTTP 状态、业务 code、文案。"""

    def __init__(
        self,
        msg: str,
        *,
        code: int = 1,
        status_code: int = 400,
    ):
        self.msg = msg
        self.code = code
        self.status_code = status_code
        super().__init__(msg)


class ParamError(AppError):
    """参数 / 校验类错误（对应请求体、路径参数等）。"""

    def __init__(self, msg: str = "invalid parameters", *, code: int = 40001):
        super().__init__(msg, code=code, status_code=422)


class AuthError(AppError):
    """未认证或 token 无效。"""

    def __init__(self, msg: str = "unauthorized", *, code: int = 40101):
        super().__init__(msg, code=code, status_code=401)


class ForbiddenError(AppError):
    """已认证但权限不足。"""

    def __init__(self, msg: str = "forbidden", *, code: int = 40301):
        super().__init__(msg, code=code, status_code=403)


class ServiceError(AppError):
    """业务规则错误（与历史行为兼容：HTTP 200，body code != 0）。"""

    def __init__(self, msg: str = "error", *, code: int = 1):
        super().__init__(msg, code=code, status_code=200)


class SystemError(AppError):
    """未预期系统错误（对外文案可收敛）。"""

    def __init__(self, msg: str = "internal server error", *, code: int = 50001):
        super().__init__(msg, code=code, status_code=500)


class RateLimitError(AppError):
    """请求过于频繁（Redis 滑动/分钟桶）。"""

    def __init__(self, msg: str = "rate limit exceeded", *, code: int = 42901):
        super().__init__(msg, code=code, status_code=429)
