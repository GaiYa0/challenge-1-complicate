"""
线索表 clues：person_id 与 Neo4j User.name（及 tenant_id）一致。
"""

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from backend.core.database import Base
from backend.model.clue_enums import ClueCategory, ClueRiskLevel


class Clue(Base):
    __tablename__ = "clues"
    __table_args__ = (
        Index("ix_clues_case_id", "case_id"),
        Index("ix_clues_case_person", "case_id", "person_id"),
        Index("ix_clues_case_risk", "case_id", "risk_level"),
        Index("ix_clues_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    person_id = Column(String(256), nullable=False)

    title = Column(String(512), nullable=False)
    summary = Column(Text, nullable=True)

    category = Column(
        SAEnum(
            ClueCategory,
            name="clue_category",
            values_callable=lambda x: [e.value for e in ClueCategory],
            native_enum=False,
            length=16,
        ),
        nullable=False,
    )
    risk_level = Column(
        SAEnum(
            ClueRiskLevel,
            name="clue_risk_level",
            values_callable=lambda x: [e.value for e in ClueRiskLevel],
            native_enum=False,
            length=16,
        ),
        nullable=False,
    )
    risk_score = Column(Float, nullable=False)

    rule_hits = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    feature_snapshot = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    risk_prompts = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
