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


def count_by_user(db: Session, user_id: int) -> int:
    return int(db.query(Case).filter(Case.user_id == user_id).count())


def list_by_user_page(db: Session, user_id: int, *, offset: int, limit: int) -> list[Case]:
    return (
        db.query(Case)
        .filter(Case.user_id == user_id)
        .order_by(Case.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def count_all(db: Session) -> int:
    return int(db.query(Case).count())


def list_all_page(db: Session, *, offset: int, limit: int) -> list[Case]:
    return db.query(Case).order_by(Case.updated_at.desc()).offset(offset).limit(limit).all()


def list_all(db: Session, limit: int = 2000) -> list[Case]:
    return db.query(Case).order_by(Case.updated_at.desc()).limit(limit).all()


def get_by_id(db: Session, case_id: int) -> Case | None:
    return db.query(Case).filter(Case.id == case_id).first()


def create(
    db: Session,
    user_id: int,
    *,
    name: str,
    case_number: str | None,
    note: str | None,
    extra_metadata: dict | None = None,
) -> Case:
    row = Case(
        user_id=user_id,
        name=name,
        case_number=case_number,
        note=note,
        extra_metadata=extra_metadata,
    )
    db.add(row)
    db.flush()
    return row


def update(db: Session, row: Case, **fields: object) -> Case:
    for k, v in fields.items():
        if v is not None:
            setattr(row, k, v)
    db.flush()
    return row


def delete(db: Session, row: Case) -> None:
    db.delete(row)
    db.flush()
