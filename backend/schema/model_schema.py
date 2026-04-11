from pydantic import BaseModel, Field


class ModelTrainResult(BaseModel):
    model_name: str
    model_version: str
    feature_version: str
    eval_accuracy: float = Field(..., description="hold-out accuracy")
    eval_precision: float
    eval_recall: float
    registry_id: int
    object_path: str
    status: str


class CeleryTaskSubmitData(BaseModel):
    """异步任务已入队：用于查询结果 backend（task_id）。"""

    task_id: str
    queue: str
    state: str = "PENDING"


class ModelPredictData(BaseModel):
    prediction: int
    model_name: str | None = None
    model_version: str | None = None
    registry_status: str | None = None


class ModelVersionIn(BaseModel):
    model_name: str = "default"
    version: str


class ModelCanaryIn(BaseModel):
    model_name: str = "default"
    version: str
    traffic_percent: int = Field(10, ge=1, le=99, description="灰度流量百分比")


class ModelRegistryOut(BaseModel):
    id: int
    model_name: str
    version: str
    feature_version: str
    object_path: str
    eval_accuracy: float
    eval_precision: float
    eval_recall: float
    traffic_percent: int
    status: str
    created_at: str | None = None
