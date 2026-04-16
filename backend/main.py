"""
应用入口 —— 创建 app、lifespan、全局异常、访问日志中间件、路由注册。
"""

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from minio import Minio
from neo4j import GraphDatabase
from redis import Redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api import analyze, auth, case, feature, feedback, file, graph, health, model, realtime_ws, task
from backend.core.config import get_settings
from backend.core.database import Base
from backend.core.exceptions import AppError, RateLimitError
from backend.core.logger import log_http_access, setup_logging
from backend.core.perf_context import get_perf_metrics, reset_perf_metrics
from backend.core.response import error, request_id_from
from backend.infra.minio_client import ensure_buckets
from backend.model.models import User
from backend.repository import user_repo
from backend.service import auth_service

import backend.model.models  # noqa: F401  确保所有 ORM 表注册到 Base.metadata

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    redis_client = Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=0,
        decode_responses=True,
    )
    minio_sdk = Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )
    neo4j_driver = GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )

    app.state.settings = settings
    app.state.engine = engine
    app.state.SessionLocal = SessionLocal
    app.state.redis = redis_client
    app.state.minio = minio_sdk
    app.state.neo4j_driver = neo4j_driver

    ensure_buckets(minio_sdk)

    with engine.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(42)"))
        Base.metadata.create_all(bind=engine)
        conn.execute(text("SELECT pg_advisory_unlock(42)"))
        conn.commit()
    # 开发环境：库中从未创建 admin 时自动插入，与登录页提示一致（生产须 DEBUG=false）
    if settings.DEBUG:
        with SessionLocal() as db:
            if user_repo.get_user_by_username(db, "admin") is None:
                db.add(
                    User(
                        username="admin",
                        password=auth_service.hash_password("admin"),
                        role="admin",
                    )
                )
                db.commit()
                logger.info("dev_seed_created username=admin")
    logger.info("schema_init_done")
    yield

    from backend.events.producer import close_producer

    close_producer()
    neo4j_driver.close()
    redis_client.close()
    engine.dispose()


app = FastAPI(lifespan=lifespan)

# 本地 Vite（5173）跨域；生产在 DEBUG=false 时通过 CORS_ORIGINS 配置（逗号分隔）
_settings = get_settings()
if _settings.DEBUG:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
elif _settings.cors_origins_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# ── 探针与指标（K8s / Prometheus）──────────────────────────────────────────

@app.get("/live")
async def liveness():
    """存活探针：不依赖外部服务。"""
    return {"status": "live"}


@app.get("/ready")
async def readiness():
    """就绪探针：可扩展为检查 DB/Redis；默认与 live 一致避免冷启动误杀。"""
    return {"status": "ready"}


@app.get("/metrics")
async def prometheus_metrics():
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ── 全局异常处理（统一 body：code / msg / data / request_id）────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    rid = request_id_from(request)
    errs = exc.errors()
    msg = errs[0].get("msg", "validation error") if errs else "validation error"
    body = error(42201, msg, rid, data=jsonable_encoder(errs)).model_dump(mode="json")
    return JSONResponse(status_code=422, content=body)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    rid = request_id_from(request)
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    status = exc.status_code
    code_map = {401: 40101, 403: 40301, 404: 40401, 422: 42201}
    biz_code = code_map.get(status, 1)
    body = error(biz_code, detail, rid).model_dump(mode="json")
    return JSONResponse(status_code=status, content=body)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    rid = request_id_from(request)
    body = error(exc.code, exc.msg, rid).model_dump(mode="json")
    return JSONResponse(status_code=exc.status_code, content=body)


@app.exception_handler(RateLimitError)
async def rate_limit_error_handler(request: Request, exc: RateLimitError):
    rid = request_id_from(request)
    body = error(exc.code, exc.msg, rid).model_dump(mode="json")
    return JSONResponse(status_code=exc.status_code, content=body)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled: %s", exc)
    rid = request_id_from(request)
    body = error(50001, "internal server error", rid).model_dump(mode="json")
    return JSONResponse(status_code=500, content=body)


# ── 请求日志中间件（request_id / 耗时 / 用户 / 路径）──────────────────────────

@app.middleware("http")
async def access_log_middleware(request: Request, call_next):
    reset_perf_metrics()
    t0 = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        latency_ms = (time.perf_counter() - t0) * 1000.0
        user = getattr(request.state, "user", None)
        user_id = getattr(user, "id", None) if user is not None else None
        perf = get_perf_metrics() or {}
        hits = int(perf.get("cache_hits", 0))
        misses = int(perf.get("cache_misses", 0))
        db_ms = float(perf.get("db_ms", 0.0))
        total = hits + misses
        hit_ratio = round(hits / total, 4) if total else None
        log_http_access(
            request_id=request.state.request_id,
            path=request.url.path,
            latency_ms=latency_ms,
            user_id=user_id,
            cache_hits=hits,
            cache_misses=misses,
            cache_hit_ratio=hit_ratio,
            db_query_ms=db_ms if db_ms > 0 else None,
        )
        if get_settings().COST_METRICS_ENABLED:
            try:
                from backend.tasks.cost_tasks import ingest_cost_metric_v1

                hdr_in = request.headers.get("content-length")
                bytes_in = int(hdr_in) if hdr_in and str(hdr_in).isdigit() else None
                hdr_out = (
                    response.headers.get("content-length")
                    if response is not None and hasattr(response, "headers")
                    else None
                )
                bytes_out = int(hdr_out) if hdr_out and str(hdr_out).isdigit() else None
                uid_metric = user_id
                if uid_metric is None:
                    uid_metric = getattr(request.state, "jwt_user_id", None)
                ingest_cost_metric_v1.delay(
                    user_id=uid_metric,
                    event_kind="http",
                    name=request.url.path,
                    duration_ms=float(latency_ms),
                    bytes_in=bytes_in,
                    bytes_out=bytes_out,
                    meta={
                        "request_id": request.state.request_id,
                        "cache_hits": hits,
                        "cache_misses": misses,
                        "cache_hit_ratio": hit_ratio,
                    },
                )
            except Exception:
                logger.debug("cost_metric_enqueue_skipped", exc_info=True)
        if hit_ratio is not None and response is not None:
            response.headers["X-Cache-Hit-Ratio"] = str(hit_ratio)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    from backend.core.exceptions import RateLimitError
    from backend.core.response import error, request_id_from
    from backend.middleware.jwt_gate import is_public_path
    from backend.middleware.rate_limit import enforce_per_user_per_minute

    if request.method == "OPTIONS" or is_public_path(request.url.path):
        return await call_next(request)
    uid = getattr(request.state, "jwt_user_id", None)
    if uid is not None:
        try:
            enforce_per_user_per_minute(request.app.state.redis, user_id=int(uid))
        except RateLimitError as e:
            from backend.core.security_audit import log_security_event

            log_security_event("rate_limited", user_id=int(uid), path=request.url.path)
            rid = request_id_from(request)
            body = error(e.code, e.msg, rid).model_dump(mode="json")
            return JSONResponse(status_code=e.status_code, content=body)
    return await call_next(request)


@app.middleware("http")
async def jwt_gate_middleware(request: Request, call_next):
    from backend.middleware.jwt_gate import jwt_gate_middleware as _jwt

    return await _jwt(request, call_next)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """最后注册 = 最先执行；确保 JWT/限流等中间件也能读到 request_id。"""
    request.state.request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.middleware("http")
async def degraded_mode_middleware(request: Request, call_next):
    """压力过大时关闭非核心路由。"""
    settings = get_settings()
    if settings.DEGRADED and settings.DEGRADE_GRAPH and request.url.path.startswith("/graph"):
        return JSONResponse(
            status_code=503,
            content={"code": 50399, "msg": "service degraded: graph temporarily unavailable"},
        )
    return await call_next(request)


# ── 路由注册 ─────────────────────────────────────────

app.include_router(auth.router)
app.include_router(case.router)
app.include_router(realtime_ws.router)
app.include_router(health.router)
app.include_router(file.router)
app.include_router(analyze.router)
app.include_router(graph.router)
app.include_router(model.router)
app.include_router(feature.router)
app.include_router(feedback.router)
app.include_router(task.router)
