from pydantic import BaseModel


class FileUploadData(BaseModel):
    """上传结果：逻辑文件名 + 预签名 URL + 库内定位字段（不返回可拼接的真实访问路径）。"""

    filename: str
    presigned_url: str
    bucket_name: str
    object_name: str
    version: str
    dataset: str = "default"
    data_layer: str = "raw"


class FileDetailItem(BaseModel):
    filename: str
    bucket_name: str
    object_name: str
    version: str
    dataset: str
    data_layer: str
    upload_time: str | None = None
    presigned_url: str
    lifecycle_tier: str | None = None
    archive_format: str | None = None
    warm_month_key: str | None = None


class PreviewData(BaseModel):
    columns: list[str]
    dtypes: dict[str, str]
    shape: list[int]
    preview: list[dict]


class CleanData(BaseModel):
    before: int
    after: int


class ColumnStats(BaseModel):
    mean: float | None = None
    max: float | None = None
    min: float | None = None


class AnomalyData(BaseModel):
    anomaly_count: int
