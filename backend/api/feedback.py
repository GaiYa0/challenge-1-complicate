"""
API 层 —— Feedback 路由
职责：只处理 HTTP，业务委托给 feedback_service。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.core.deps import get_db
from backend.model.models import User
from backend.schema.common import ApiResponse, success_for_request
from backend.schema.feedback import FeedbackIn
from backend.service import feedback_service

router = APIRouter()


@router.post("/feedback", response_model=ApiResponse[None])
def post_feedback(
    request: Request,
    body: FeedbackIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    feedback_service.create_feedback(db, current_user, body)
    return success_for_request(request, None)
