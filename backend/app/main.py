"""
应用入口 —— 创建 app、lifespan、全局异常、访问日志中间件、路由注册。
"""

import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from ipaddress import ip_address, ip_network

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

from backend.app.routers import (
    analyze,
    auth,
    case,
    clue_routes,
    compliance,
    feature,
    feedback,
    file,
    graph,
    graph_case_routes,
    health,
    model,
    realtime_ws,
    reports,
    task,
    users_alias,
)
from backend.core.config import get_settings
from backend.core.database import Base
from backend.core.exceptions import AppError, RateLimitError
from backend.core.logger import log_http_access, setup_logging
from backend.core.perf_context import get_perf_metrics, reset_perf_metrics
from backend.core.response import error, request_id_from
from backend.infra.minio_client import ensure_buckets
from backend.model.models import User
from backend.app.repositories import user_repo
from backend.app.services import auth_service

import backend.model.models  # noqa: F401  确保所有 ORM 表注册到 Base.metadata

setup_logging()
logger = logging.getLogger(__name__)

_REQUEST_ID_INCOMING = re.compile(r"^[a-zA-Z0-9_.:-]+$")


def _parse_trusted_networks(raw: str) -> list:
    nets = []
    for item in str(raw or "").split(","):
        s = item.strip()
        if not s:
            continue
        try:
            nets.append(ip_network(s, strict=False))
        except ValueError:
            continue
    return nets


def _peer_trusted(request: Request, nets: list) -> bool:
    if not request.client or not nets:
        return False
    try:
        peer = ip_address(request.client.host)
    except ValueError:
        return False
    return any(peer in n for n in nets)


_ADDITIVE_COLUMN_PATCHES: tuple[tuple[str, str, str], ...] = (
    ("cases", "extra_metadata", "JSONB"),
    ("cases", "status", "VARCHAR(32) NOT NULL DEFAULT 'active'"),
    ("cases", "is_demo", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("audit_logs", "case_id", "INTEGER"),
    ("audit_logs", "resource_id", "VARCHAR(128)"),
    ("audit_logs", "ip_address", "VARCHAR(64)"),
    ("audit_logs", "user_agent", "VARCHAR(512)"),
    ("audit_logs", "detail", "JSONB"),
)


def _apply_additive_schema_patches(conn) -> None:
    for table, column, ddl in _ADDITIVE_COLUMN_PATCHES:
        try:
            conn.execute(
                text(f'ALTER TABLE IF EXISTS "{table}" ADD COLUMN IF NOT EXISTS "{column}" {ddl}')
            )
        except Exception:
            logger.debug("additive_patch_failed table=%s column=%s", table, column, exc_info=True)
    try:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS field_mapping_memory (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    header_signature VARCHAR(512) NOT NULL,
                    source_field VARCHAR(256) NOT NULL,
                    target_field VARCHAR(128) NOT NULL,
                    confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
                    hit_count INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL DEFAULT now(),
                    updated_at TIMESTAMP NOT NULL DEFAULT now(),
                    last_used_at TIMESTAMP NOT NULL DEFAULT now()
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_fmm_user_signature ON field_mapping_memory (user_id, header_signature)"
            )
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_fmm_last_used ON field_mapping_memory (last_used_at)")
        )
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_fmm_user_header_source ON field_mapping_memory (user_id, header_signature, source_field)"
            )
        )
    except Exception:
        logger.debug("additive_table_patch_failed table=field_mapping_memory", exc_info=True)


def _resolve_request_id(request: Request) -> str:
    settings = get_settings()
    max_len = int(getattr(settings, "REQUEST_ID_MAX_LEN", 128))
    nets = _parse_trusted_networks(getattr(settings, "TRUSTED_PROXY_IPS", ""))
    if _peer_trusted(request, nets):
        raw = request.headers.get("x-request-id") or request.headers.get("X-Request-ID")
        if raw:
            s = raw.strip()
            if 0 < len(s) <= max_len and _REQUEST_ID_INCOMING.match(s):
                return s
    return str(uuid.uuid4())


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
    )
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

    try:
        try:
            ensure_buckets(minio_sdk)
        except Exception:
            logger.exception("ensure_buckets_failed_continuing")

        with engine.connect() as conn:
            conn.execute(text("SELECT pg_advisory_lock(42)"))
            try:
                Base.metadata.create_all(bind=engine)
                _apply_additive_schema_patches(conn)
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(42)"))
            conn.commit()
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
    finally:
        try:
            from backend.events.producer import close_producer

            close_producer()
        except Exception:
            logger.debug("close_producer_failed", exc_info=True)
        try:
            neo4j_driver.close()
        except Exception:
            logger.debug("neo4j_close_failed", exc_info=True)
        try:
            redis_client.close()
        except Exception:
            logger.debug("redis_close_failed", exc_info=True)
        try:
            engine.dispose()
        except Exception:
            logger.debug("engine_dispose_failed", exc_info=True)


app = FastAPI(lifespan=lifespan)

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


@app.get("/live")
async def liveness():
    """进程级探活：只要应用能响应就算活着，不触碰任何外部依赖。"""
    from backend.app.services.health_probe import check_liveness

    return check_liveness()


@app.get("/ready")
async def readiness():
    """
    业务级就绪：并发探 DB/Redis/MinIO/Neo4j，带 1.5s 超时与 5s 结果缓存。
    DB 不可达 → 503，其它依赖失联仅在 payload 里呈现，不影响路由入站。
    """
    from backend.app.services.health_probe import check_readiness

    payload, is_ready = check_readiness(app)
    if not is_ready:
        return JSONResponse(status_code=503, content=payload)
    return payload


@app.get("/ready/deep")
async def readiness_deep():
    """强制跳过缓存的深度探活，供运维按需触发。"""
    from backend.app.services.health_probe import check_readiness

    payload, is_ready = check_readiness(app, force=True)
    if not is_ready:
        return JSONResponse(status_code=503, content=payload)
    return payload


@app.get("/metrics")
async def prometheus_metrics():
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


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
        user_id = getattr(request.state, "jwt_user_id", None)
        if user_id is None:
            user = getattr(request.state, "user", None)
            try:
                user_id = getattr(user, "id", None) if user is not None else None
            except Exception:
                user_id = None
        perf = get_perf_metrics() or {}
        hits = int(perf.get("cache_hits", 0))
        misses = int(perf.get("cache_misses", 0))
        db_ms = float(perf.get("db_ms", 0.0))
        total = hits + misses
        hit_ratio = round(hits / total, 4) if total else None
        log_http_access(
            request_id=getattr(request.state, "request_id", "-"),
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
                        "request_id": getattr(request.state, "request_id", "-"),
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
    from backend.core.response import error, request_id_from
    from backend.middleware.jwt_gate import is_public_path
    from backend.middleware.rate_limit import check_rate_limit, is_exempt

    path = request.url.path
    if request.method == "OPTIONS" or is_public_path(path) or is_exempt(path):
        return await call_next(request)
    uid = getattr(request.state, "jwt_user_id", None)
    if uid is None:
        return await call_next(request)
    try:
        decision = check_rate_limit(request.app.state.redis, user_id=int(uid), path=path)
    except Exception:
        logger.debug("rate_limit_check_failed", exc_info=True)
        return await call_next(request)
    if not decision.blocked:
        return await call_next(request)

    from backend.core.security_audit import log_security_event

    log_security_event(
        "rate_limited",
        user_id=int(uid),
        path=path,
        bucket=decision.bucket_kind,
    )
    rid = request_id_from(request)
    body = error(42901, "rate limit exceeded", rid).model_dump(mode="json")
    retry_after = max(1, int(decision.retry_after))
    headers = {"Retry-After": str(retry_after), "X-RateLimit-Bucket": decision.bucket_kind}
    return JSONResponse(status_code=429, content=body, headers=headers)


@app.middleware("http")
async def jwt_gate_middleware(request: Request, call_next):
    from backend.middleware.jwt_gate import jwt_gate_middleware as _jwt

    return await _jwt(request, call_next)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """最后注册 = 最先执行；确保 JWT/限流等中间件也能读到 request_id。"""
    request.state.request_id = _resolve_request_id(request)
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
app.include_router(clue_routes.router)
app.include_router(graph_case_routes.router)
app.include_router(realtime_ws.router)
app.include_router(health.router)
# 同一份 health 路由以 /health 前缀再挂一次，对齐 `GET /api/health/analysis/fund` 历史调用
app.include_router(health.router, prefix="/health")
app.include_router(file.router)
app.include_router(analyze.router)
app.include_router(graph.router)
app.include_router(model.router)
app.include_router(feature.router)
app.include_router(feedback.router)
app.include_router(task.router)
app.include_router(reports.router)
app.include_router(compliance.router)
# /users、/tasks/active 等复数形式对外别名
app.include_router(users_alias.users_router)
app.include_router(users_alias.tasks_router)
