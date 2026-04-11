"""
file-service：健康检查、内部 Kafka 发布演示；日志 JSON + request_id。
启动：uvicorn services.file_service.main:app --port 8002
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from services.common.kafka_bus import close_producer
from services.common.logging_setup import configure_logging
from services.common.tracing import RequestIdMiddleware, get_request_id
from services.file_service.api.pipeline_events import router as pipeline_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging("file-service")
    yield
    close_producer()


app = FastAPI(title="file-service", lifespan=lifespan)
app.add_middleware(RequestIdMiddleware)
app.include_router(pipeline_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "file-service", "request_id": get_request_id()}
