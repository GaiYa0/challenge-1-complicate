from typing import Any

from pydantic import BaseModel


class FeatureData(BaseModel):
    features: dict[str, Any]


class FeatureMapData(BaseModel):
    """get_features 接口返回：某实体在指定版本下的特征字典。"""

    entity_id: int
    version: str
    features: dict[str, Any]
