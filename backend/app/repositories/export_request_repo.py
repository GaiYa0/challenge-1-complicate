from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.model.export_request import ExportRequest


def create(
    db: Session,
    *,
    applicant_id: int,
    case_id: int,
    person_id: str,
    file_format: str,
) -> ExportRequest:
    row = ExportRequest(
        applicant_id=applicant_id,
        case_id=case_id,
        person_id=person_id,
        file_format=file_format,
        status="pending",
    )
    db.add(row)
    db.flush()
    return row


def get_by_id(db: Session, rid: int) -> ExportRequest | None:
    return db.query(ExportRequest).filter(ExportRequest.id == rid).first()


def list_for_user(db: Session, user_id: int, limit: int = 100) -> list[ExportRequest]:
    return (
        db.query(ExportRequest)
        .filter(ExportRequest.applicant_id == user_id)
        .order_by(ExportRequest.created_at.desc())
        .limit(limit)
        .all()
    )


def list_pending(db: Session, limit: int = 200) -> list[ExportRequest]:
    return (
        db.query(ExportRequest)
        .filter(ExportRequest.status == "pending")
        .order_by(ExportRequest.created_at.asc())
        .limit(limit)
        .all()
    )


def list_all(db: Session, limit: int = 500) -> list[ExportRequest]:
    return (
        db.query(ExportRequest).order_by(ExportRequest.created_at.desc()).limit(limit).all()
    )


def set_status(
    db: Session,
    row: ExportRequest,
    *,
    status: str,
    reviewer_id: int | None,
    review_note: str | None = None,
) -> ExportRequest:
    row.status = status
    row.reviewer_id = reviewer_id
    row.review_note = review_note
    row.reviewed_at = datetime.now(timezone.utc)
    db.flush()
    return row
