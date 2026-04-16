from __future__ import annotations

from sqlalchemy.orm import Session

from backend.model.case import Case


def list_by_user(db: Session, user_id: int) -> list[Case]:
    return (
        db.query(Case)
        .filter(Case.user_id == user_id)
        .order_by(Case.updated_at.desc())
        .all()
    )


def get_by_id(db: Session, case_id: int) -> Case | None:
    return db.query(Case).filter(Case.id == case_id).first()


def create(db: Session, user_id: int, *, name: str, case_number: str | None, note: str | None) -> Case:
    row = Case(user_id=user_id, name=name, case_number=case_number, note=note)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update(db: Session, row: Case, **fields: object) -> Case:
    for k, v in fields.items():
        if v is not None:
            setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


def delete(db: Session, row: Case) -> None:
    db.delete(row)
    db.commit()
