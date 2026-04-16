from pydantic import BaseModel, Field


class HealthData(BaseModel):
    status: str


class TestData(BaseModel):
    msg: str


class PieSlice(BaseModel):
    name: str
    value: int = Field(ge=0)


class AnalysisTableRow(BaseModel):
    id: int
    name: str
    metric: int
    status: str


class AnalysisDashboardData(BaseModel):
    """分析看板：结构化数据供前端图表消费（示例数据由服务端统一生成）。"""

    headline: str
    trend_labels: list[str]
    trend_values: list[int]
    bar_labels: list[str]
    bar_values: list[int]
    pie: list[PieSlice]
    table: list[AnalysisTableRow]
