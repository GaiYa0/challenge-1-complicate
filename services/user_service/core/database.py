from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from services.user_service.core.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache(maxsize=1)
def get_engine():
    return create_engine(get_settings().DATABASE_URL, pool_pre_ping=True)


@lru_cache(maxsize=1)
def _session_factory():
    return sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


def get_db():
    db = _session_factory()()
    try:
        yield db
    finally:
        db.close()
