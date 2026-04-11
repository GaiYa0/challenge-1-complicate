"""
Repository 层 —— User 数据访问
职责：只负责 User 表的查询。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.model.models import User


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.execute(select(User).where(User.username == username)).scalar_one_or_none()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
