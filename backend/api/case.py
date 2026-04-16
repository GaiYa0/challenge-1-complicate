"""案件管理路由：CRUD for investigation cases."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.core.deps import get_db
from backend.core.exceptions import AppError
from backend.core.response import success_for_request
from backend.model.models import User
from backend.repository import case_repo
from backend.schema.case import CaseCreate, CaseOut, CaseUpdate
from backend.schema.common import ApiResponse

router = APIRouter(prefix="/case", tags=["case"])


def _to_out(row) -> CaseOut:
    return CaseOut(
        id=row.id,
        name=row.name,
        case_number=row.case_number,
        note=row.note,
        status=row.status,
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


@router.get("", response_model=ApiResponse[list[CaseOut]])
def list_cases(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = case_repo.list_by_user(db, current_user.id)
    return success_for_request(request, [_to_out(r) for r in rows])


@router.post("", response_model=ApiResponse[CaseOut])
def create_case(
    request: Request,
    body: CaseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = case_repo.create(
        db,
        current_user.id,
        name=body.name,
        case_number=body.case_number,
        note=body.note,
    )
    return success_for_request(request, _to_out(row))


@router.get("/{case_id}", response_model=ApiResponse[CaseOut])
def get_case(
    request: Request,
    case_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = case_repo.get_by_id(db, case_id)
    if row is None or row.user_id != current_user.id:
        raise AppError("案件不存在", code=40401, status_code=404)
    return success_for_request(request, _to_out(row))


@router.put("/{case_id}", response_model=ApiResponse[CaseOut])
def update_case(
    request: Request,
    case_id: int,
    body: CaseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = case_repo.get_by_id(db, case_id)
    if row is None or row.user_id != current_user.id:
        raise AppError("案件不存在", code=40401, status_code=404)
    row = case_repo.update(
        db,
        row,
        name=body.name,
        case_number=body.case_number,
        note=body.note,
        status=body.status,
    )
    return success_for_request(request, _to_out(row))


@router.delete("/{case_id}", response_model=ApiResponse[None])
def delete_case(
    request: Request,
    case_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = case_repo.get_by_id(db, case_id)
    if row is None or row.user_id != current_user.id:
        raise AppError("案件不存在", code=40401, status_code=404)
    case_repo.delete(db, row)
    return success_for_request(request, None, msg="deleted")
