from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String
from sqlalchemy.sql import func

from backend.core.database import Base


class Feedback(Base):
    __tablename__ = "feedbacks"
    __table_args__ = (
        Index("ix_feedbacks_user_filename", "user_id", "filename"),
        Index("ix_feedbacks_created_at", "created_at"),
        Index("ix_feedbacks_is_correct", "is_correct"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    filename = Column(String(512), nullable=False)
    label = Column(Integer, nullable=False)
    is_correct = Column(Boolean, nullable=True)
    prediction = Column(Integer, nullable=True)
    model_name = Column(String(128), nullable=True)
    model_version = Column(String(32), nullable=True)
    entity_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
