"""
依赖注入：DB Session / Redis / MinIO / Neo4j
连接在 FastAPI lifespan 中挂到 app.state，此处通过 Request 取出，避免模块级全局客户端。
"""

from collections.abc import Generator

from fastapi import Request
from minio import Minio
from neo4j import Driver
from redis import Redis
from sqlalchemy.orm import Session


def get_db(request: Request) -> Generator[Session, None, None]:
    """
    每个请求独立 Session：
    - 路由正常返回时统一提交（repo 层只 flush，提交权在请求边界）
    - 路由异常时回滚
    - 无论成败都关闭会话
    """
    SessionLocal = request.app.state.SessionLocal
    db = SessionLocal()
    try:
        yield db
        try:
            if db.in_transaction():
                db.commit()
        except Exception:
            db.rollback()
            raise
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise
    finally:
        db.close()


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


def get_minio(request: Request) -> Minio:
    return request.app.state.minio


def get_neo4j_driver(request: Request) -> Driver:
    return request.app.state.neo4j_driver
