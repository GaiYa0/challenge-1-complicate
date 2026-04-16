"""
Repository 层 —— Feedback 数据访问
职责：不在此 commit。
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.model.models import Feedback


def insert_feedback(
    db: Session,
    *,
    user_id: int,
    filename: str,
    label: int,
    is_correct: bool | None = None,
    prediction: int | None = None,
    model_name: str | None = None,
    model_version: str | None = None,
    entity_id: int | None = None,
) -> Feedback:
    rec = Feedback(
        user_id=user_id,
        filename=filename,
        label=label,
        is_correct=is_correct,
        prediction=prediction,
        model_name=model_name,
        model_version=model_version,
        entity_id=entity_id,
    )
    db.add(rec)
    db.flush()
    return rec


def count_recent_incorrect(db: Session, *, user_id: int | None = None, hours: int = 24) -> int:
    """近 window 内标注为错误（is_correct=False）的条数，用于触发再训练。"""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    q = select(func.count()).select_from(Feedback).where(
        Feedback.is_correct.is_(False),
        Feedback.created_at >= since,
    )
    if user_id is not None:
        q = q.where(Feedback.user_id == user_id)
    return int(db.execute(q).scalar_one() or 0)
