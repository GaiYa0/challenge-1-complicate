"""
演示：file-service 通过 Kafka 投递数据处理事件（异步），headers 携带 request_id。
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from services.common.kafka_bus import publish_event
from services.common.kafka_topics import MS_DATA_PIPELINE
from services.file_service.api.deps_internal import verify_internal_token
from services.file_service.core.config import get_file_settings

_log = logging.getLogger("file.kafka")

router = APIRouter(
    prefix="/internal/v1/pipeline",
    tags=["internal-pipeline"],
    dependencies=[Depends(verify_internal_token)],
)


class PublishBody(BaseModel):
    resource_id: str = Field(min_length=1)


@router.post("/publish")
def publish_data_pipeline(body: PublishBody):
    s = get_file_settings()
    if not s.KAFKA_ENABLED:
        return {"published": False, "reason": "kafka_disabled"}
    publish_event(
        bootstrap_servers=s.KAFKA_BOOTSTRAP_SERVERS,
        topic=MS_DATA_PIPELINE,
        payload={"type": "data_pipeline", "resource_id": body.resource_id},
        key=body.resource_id,
    )
    return {"published": True, "topic": MS_DATA_PIPELINE, "resource_id": body.resource_id}
