"""
Service 层 —— 健康检查 / 测试
职责：/test 的 Redis 缓存逻辑在此处理，API 层不直接访问 Redis。
"""

from redis import Redis

from backend.core.config import CACHE_TTL_TEST
from backend.app.schemas.health import AnalysisDashboardData, AnalysisTableRow, PieSlice, TestData


def get_test_data(redis: Redis) -> TestData:
    cached = redis.get("test_cache")
    if cached is not None:
        return TestData.model_validate_json(cached)
    data = TestData(msg="test ok")
    redis.setex("test_cache", CACHE_TTL_TEST, data.model_dump_json())
    return data


def get_analysis_dashboard() -> AnalysisDashboardData:
    """返回分析页图表/表格用数据（当前为稳定示例，后续可接 DB / 任务统计）。"""
    return AnalysisDashboardData(
        headline="分析看板（服务端数据）",
        trend_labels=["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
        trend_values=[120, 200, 150, 80, 70, 110, 160],
        bar_labels=["华东", "华北", "华南", "西南", "西北"],
        bar_values=[320, 280, 150, 90, 60],
        pie=[
            PieSlice(name="直连", value=48),
            PieSlice(name="搜索", value=32),
            PieSlice(name="外链", value=20),
        ],
        table=[
            AnalysisTableRow(id=1, name="任务 A", metric=128, status="完成"),
            AnalysisTableRow(id=2, name="任务 B", metric=96, status="运行中"),
            AnalysisTableRow(id=3, name="任务 C", metric=64, status="排队"),
        ],
    )
