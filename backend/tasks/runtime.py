"""
Celery Worker 运行时：DB / Redis / MinIO 单例（与 Web 进程隔离）。
"""

from __future__ import annotations

import logging

import redis
from minio import Minio
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import get_settings
from backend.infra import minio_client as minio_ops
from backend.app.repositories import file_repo

logger = logging.getLogger("celery.worker")

_engine = None
_session_factory = None
_worker_redis: redis.Redis | None = None
_worker_minio: Minio | None = None
_buckets_ready = False


def db_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    return _engine


def db_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine())
    return _session_factory


def redis_client() -> redis.Redis:
    global _worker_redis
    if _worker_redis is None:
        s = get_settings()
        _worker_redis = redis.Redis(host=s.REDIS_HOST, port=s.REDIS_PORT, db=0, decode_responses=True)
    return _worker_redis


def minio_client() -> Minio:
    global _worker_minio, _buckets_ready
    if _worker_minio is None:
        s = get_settings()
        _worker_minio = Minio(
            s.MINIO_ENDPOINT,
            access_key=s.MINIO_ACCESS_KEY,
            secret_key=s.MINIO_SECRET_KEY,
            secure=s.MINIO_SECURE,
        )
    if not _buckets_ready:
        minio_ops.ensure_buckets(_worker_minio)
        _buckets_ready = True
    return _worker_minio


def file_belongs_to_user(filename: str, user_id: int) -> bool:
    db = open_session()
    try:
        return file_repo.get_file_for_tenant(db, filename, user_id) is not None
    finally:
        db.close()


def open_session() -> Session:
    """调用方负责 session.close()。"""
    return db_session_factory()()
