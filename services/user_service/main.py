"""
user-service 入口：uvicorn services.user_service.main:app --port 8001
（PYTHONPATH 需包含项目根目录）
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from services.common.logging_setup import configure_logging
from services.common.tracing import RequestIdMiddleware
from services.user_service.api import auth, chain_demo, health, internal
from services.user_service.core.database import Base, get_engine
from services.user_service.model import user as user_model  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging("user-service")
    Base.metadata.create_all(bind=get_engine())
    yield


app = FastAPI(title="user-service", lifespan=lifespan)
app.add_middleware(RequestIdMiddleware)
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(internal.router)
app.include_router(chain_demo.router)
