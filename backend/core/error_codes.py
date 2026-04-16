"""
业务错误码约定（与 HTTP 状态、AppError.code 配合使用）。

分段规则（可扩展，禁止随意占用他段）：
- 0        成功
- 40xxx    参数 / 校验
- 401xx    认证
- 403xx    授权
- 404xx    资源不存在
- 409xx    冲突（幂等、重复绑定等）
- 42xxx    案件（case）
- 43xxx    文件 / 存储
- 44xxx    分析任务
- 45xxx    线索
- 46xxx    图 / 投影
- 50xxx    系统 / 依赖不可用
"""

from enum import IntEnum


class ErrorCode(IntEnum):
    SUCCESS = 0

    # 参数
    INVALID_PARAMS = 40001

    # 认证 / 授权
    UNAUTHORIZED = 40101
    FORBIDDEN = 40301

    # 资源
    NOT_FOUND = 40401

    # 冲突
    CONFLICT = 40901

    # 案件
    CASE_NOT_FOUND = 42001
    CASE_ACCESS_DENIED = 42002

    # 文件
    FILE_NOT_FOUND = 43001
    FILE_ACCESS_DENIED = 43002

    # 分析任务
    ANALYSIS_TASK_NOT_FOUND = 44001
    ANALYSIS_TASK_INVALID_STATE = 44002

    # 线索
    CLUE_NOT_FOUND = 45001

    # 图
    GRAPH_QUERY_FAILED = 46001

    # 系统
    INTERNAL_ERROR = 50001
    DEPENDENCY_UNAVAILABLE = 50002
