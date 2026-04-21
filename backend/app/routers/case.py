"""案件管理路由：CRUD for investigation cases。"""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from backend.app.routers.deps import get_current_user
from backend.core.deps import get_db
from backend.core.exceptions import AppError
from backend.core.response import success_for_request
from backend.core.tenant_access import is_admin
from backend.model.models import User
from backend.app.repositories import case_repo
from backend.app.schemas.case import CaseCreate, CaseOut, CaseUpdate
from backend.app.schemas.common import ApiResponse, PagedData

router = APIRouter(prefix="/case", tags=["case"])


def _to_out(row) -> CaseOut:
    return CaseOut(
        id=row.id,
        name=row.name,
        case_number=row.case_number,
        note=row.note,
        status=row.status,
        extra_metadata=row.extra_metadata,
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


@router.get("", response_model=ApiResponse[PagedData[CaseOut]])
def list_cases(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    scope: str | None = Query(
        None,
        description="不传或 mine：本人案件；all：管理员查看全部",
    ),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(24, ge=1, le=100, description="每页条数"),
):
    offset = (page - 1) * page_size
    if scope == "all" and is_admin(current_user):
        total = case_repo.count_all(db)
        rows = case_repo.list_all_page(db, offset=offset, limit=page_size)
    else:
        total = case_repo.count_by_user(db, current_user.id)
        rows = case_repo.list_by_user_page(db, current_user.id, offset=offset, limit=page_size)
    return success_for_request(
        request,
        PagedData(
            items=[_to_out(r) for r in rows],
            total=total,
            page=page,
            page_size=page_size,
        ),
    )


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
        extra_metadata=None,
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
    if row is None:
        raise AppError("案件不存在", code=40401, status_code=404)
    if not is_admin(current_user) and row.user_id != current_user.id:
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
    if row is None:
        raise AppError("案件不存在", code=40401, status_code=404)
    if not is_admin(current_user) and row.user_id != current_user.id:
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


@router.patch("/{case_id}", response_model=ApiResponse[CaseOut])
def patch_case(
    request: Request,
    case_id: int,
    body: CaseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = case_repo.get_by_id(db, case_id)
    if row is None:
        raise AppError("案件不存在", code=40401, status_code=404)
    if not is_admin(current_user) and row.user_id != current_user.id:
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
    if row is None:
        raise AppError("案件不存在", code=40401, status_code=404)
    if not is_admin(current_user) and row.user_id != current_user.id:
        raise AppError("案件不存在", code=40401, status_code=404)
    case_repo.delete(db, row)
    return success_for_request(request, None, msg="deleted")
