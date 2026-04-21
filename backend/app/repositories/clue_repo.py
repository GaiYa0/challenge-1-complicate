from __future__ import annotations

from sqlalchemy.orm import Session

from backend.model.clue import Clue


def list_by_case(db: Session, *, case_id: int) -> list[Clue]:
    return (
        db.query(Clue)
        .filter(Clue.case_id == case_id)
        .order_by(Clue.risk_score.desc(), Clue.id.asc())
        .all()
    )


def list_by_case_and_person(db: Session, *, case_id: int, person_id: str) -> list[Clue]:
    return (
        db.query(Clue)
        .filter(Clue.case_id == case_id, Clue.person_id == person_id)
        .order_by(Clue.risk_score.desc(), Clue.id.asc())
        .all()
    )


def get_by_id(db: Session, clue_id: int) -> Clue | None:
    return db.query(Clue).filter(Clue.id == clue_id).first()


def get_by_id_and_case(db: Session, clue_id: int, case_id: int) -> Clue | None:
    return db.query(Clue).filter(Clue.id == clue_id, Clue.case_id == case_id).first()


def bulk_add(db: Session, rows: list[Clue]) -> None:
    if not rows:
        return
    db.add_all(rows)
    db.flush()
