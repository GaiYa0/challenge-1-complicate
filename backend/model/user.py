from sqlalchemy import Column, DateTime, Index, Integer, String
from sqlalchemy.sql import func

from backend.core.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(128), nullable=False, unique=True)
    password = Column(String(256), nullable=False)
    role = Column(String(32), nullable=False, server_default="user")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
