from __future__ import annotations

import hashlib
import logging

from neo4j import Driver
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.core.exceptions import AppError, ForbiddenError
from backend.core.tenant_access import is_admin
from backend.model.models import User
from backend.app.repositories import case_repo, clue_repo
from backend.app.services import graph_service
from backend.app.services.clue_mock import generate_mock_clues

_log = logging.getLogger(__name__)


def _ensure_case_owned(db: Session, user: User, case_id: int):
    row = case_repo.get_by_id(db, case_id)
    if row is None:
        raise AppError("案件不存在", code=42001, status_code=404)
    if not is_admin(user) and row.user_id != user.id:
        raise ForbiddenError("无权访问该案件", code=42002)
    return row


def _seed_mock_if_empty(db: Session, *, case_id: int, person_id: str) -> list:
    """使用 Postgres advisory lock 串行化首批写入，避免并发下重复插入。"""
    rows = clue_repo.list_by_case_and_person(db, case_id=case_id, person_id=person_id)
    if rows:
        return rows
    key_raw = f"{case_id}|{person_id}".encode("utf-8")
    lock_key = int.from_bytes(hashlib.sha256(key_raw).digest()[:8], "big", signed=True)
    try:
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": lock_key})
    except Exception:
        _log.debug("advisory_lock_unavailable", exc_info=True)
    rows = clue_repo.list_by_case_and_person(db, case_id=case_id, person_id=person_id)
    if rows:
        return rows
    mock_rows = generate_mock_clues(case_id=case_id, person_id=person_id)
    clue_repo.bulk_add(db, mock_rows)
    db.commit()
    return clue_repo.list_by_case_and_person(db, case_id=case_id, person_id=person_id)


def list_clues_for_person(
    db: Session,
    neo4j: Driver,
    *,
    user: User,
    case_id: int,
    person_id: str,
) -> list[dict]:
    case_row = _ensure_case_owned(db, user, case_id)
    tid = int(case_row.user_id)
    if not graph_service.person_name_exists(neo4j, name=person_id, tenant_id=tid):
        raise AppError("人物不在图谱中或 person_id 与 Neo4j 不一致", code=40401, status_code=404)

    rows = _seed_mock_if_empty(db, case_id=case_id, person_id=person_id)

    return [
        {
            "id": r.id,
            "title": r.title,
            "risk_level": r.risk_level.value if hasattr(r.risk_level, "value") else str(r.risk_level),
            "risk_score": float(r.risk_score),
        }
        for r in rows
    ]


def get_clue_detail(
    db: Session,
    *,
    user: User,
    clue_id: int,
) -> dict:
    row = clue_repo.get_by_id(db, clue_id)
    if row is None:
        raise AppError("线索不存在", code=45001, status_code=404)
    _ensure_case_owned(db, user, row.case_id)

    def _cat(v) -> str:
        return v.value if hasattr(v, "value") else str(v)

    return {
        "id": row.id,
        "case_id": row.case_id,
        "person_id": row.person_id,
        "title": row.title,
        "summary": row.summary,
        "category": _cat(row.category),
        "risk_level": _cat(row.risk_level),
        "risk_score": float(row.risk_score),
        "rule_hits": row.rule_hits if isinstance(row.rule_hits, list) else [],
        "feature_snapshot": row.feature_snapshot if isinstance(row.feature_snapshot, dict) else {},
        "risk_prompts": row.risk_prompts if isinstance(row.risk_prompts, list) else [],
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
    }
