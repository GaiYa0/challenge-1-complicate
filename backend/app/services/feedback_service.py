"""
Service 层 —— Feedback 业务
职责：校验权限后写入反馈；错误反馈堆积时触发闭环检查任务（特征/重训由异步任务衔接）。
"""

import logging

from sqlalchemy.orm import Session

from backend.core.exceptions import ServiceError
from backend.core.transaction import transaction
from backend.model.models import User
from backend.app.repositories import feedback_repo
from backend.app.schemas.feedback import FeedbackIn
from backend.app.services.file_service import file_owner_user_id_if_accessible
from backend.tasks.model_tasks import check_feedback_retrain_task

_log = logging.getLogger(__name__)

_RETRAIN_CHECK_THRESHOLD = 10


def create_feedback(db: Session, user: User, body: FeedbackIn) -> None:
    if file_owner_user_id_if_accessible(db, body.filename, user) is None:
        raise ServiceError("file not found")

    if body.is_correct is not None:
        is_correct = body.is_correct
        label = 1 if is_correct else 0
    else:
        label = int(body.label)  # type: ignore[arg-type]
        is_correct = bool(label)

    with transaction(db):
        feedback_repo.insert_feedback(
            db,
            user_id=user.id,
            filename=body.filename,
            label=label,
            is_correct=is_correct,
            prediction=body.prediction,
            model_name=body.model_name,
            model_version=body.model_version,
            entity_id=body.entity_id,
        )

    if is_correct is False:
        recent_incorrect = feedback_repo.count_recent_incorrect(db, user_id=user.id)
        if recent_incorrect >= _RETRAIN_CHECK_THRESHOLD and recent_incorrect % _RETRAIN_CHECK_THRESHOLD == 0:
            _log.info("retrain_check_triggered user_id=%s incorrect_count=%s", user.id, recent_incorrect)
            check_feedback_retrain_task.delay()
