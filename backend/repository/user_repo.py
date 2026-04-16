"""
Repository 层 —— User 数据访问
职责：只负责 User 表的查询。
"""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.model.celery_task_run import CeleryTaskRun
from backend.model.cost_metric import CostMetric
from backend.model.feedback import Feedback
from backend.model.feature import Feature
from backend.model.file import File
from backend.model.models import User


def count_user_related_rows(db: Session, user_id: int) -> int:
    """文件 / 反馈 / 特征 / 任务记录等业务表仍引用该用户时不可直接删用户。"""
    total = 0
    for model in (File, Feedback, Feature):
        n = db.scalar(select(func.count()).select_from(model).where(model.user_id == user_id))
        total += int(n or 0)
    n_task = db.scalar(
        select(func.count())
        .select_from(CeleryTaskRun)
        .where(CeleryTaskRun.user_id == user_id),
    )
    total += int(n_task or 0)
    n_cost = db.scalar(
        select(func.count())
        .select_from(CostMetric)
        .where(CostMetric.user_id == user_id),
    )
    total += int(n_cost or 0)
    return total


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id.asc())).all())


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.execute(select(User).where(User.username == username)).scalar_one_or_none()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()


def delete_user_by_id(db: Session, user_id: int) -> bool:
    u = get_user_by_id(db, user_id)
    if u is None:
        return False
    try:
        db.delete(u)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    return True
