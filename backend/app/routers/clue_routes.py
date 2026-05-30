"""线索 API：GET /cases/{case_id}/persons/{person_id}/clues、GET /clues/{clue_id}（经前端 /api 代理后无 /api 前缀）。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from minio import Minio
from neo4j import Driver
from sqlalchemy.orm import Session

from backend.app.routers.deps import get_current_user
from backend.core.deps import get_db, get_minio, get_neo4j_driver
from backend.core.response import success_for_request
from backend.model.models import User
from backend.app.schemas.clue_api import ClueDetailOut, ClueListItem
from backend.app.schemas.common import ApiResponse
from backend.app.schemas.portrait import PersonPortraitOut
from backend.app.services import audit_service, clue_service, portrait_service

router = APIRouter(tags=["clues"])


@router.get(
    "/cases/{case_id}/clues",
    response_model=ApiResponse[list[ClueListItem]],
)
def list_case_clues(
    request: Request,
    case_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    minio: Minio = Depends(get_minio),
):
    rows = clue_service.ensure_case_clues(
        db,
        minio,
        case_id=case_id,
        user=current_user,
    )
    data = [
        {
            "id": r.id,
            "title": r.title,
            "risk_level": r.risk_level.value if hasattr(r.risk_level, "value") else str(r.risk_level),
            "risk_score": float(r.risk_score),
        }
        for r in rows
    ]
    return success_for_request(request, [ClueListItem.model_validate(x) for x in data])


@router.get(
    "/cases/{case_id}/persons/{person_id}/clues",
    response_model=ApiResponse[list[ClueListItem]],
)
def list_person_clues(
    request: Request,
    case_id: int,
    person_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    neo4j_driver: Driver = Depends(get_neo4j_driver),
    minio: Minio = Depends(get_minio),
):
    data = clue_service.list_clues_for_person(
        db,
        neo4j_driver,
        minio,
        user=current_user,
        case_id=case_id,
        person_id=person_id,
    )
    audit_service.record(
        db,
        request,
        current_user,
        action="query_clues_list",
        resource_type="person",
        resource_id=person_id,
        case_id=case_id,
        detail={"count": len(data)},
    )
    return success_for_request(request, [ClueListItem.model_validate(x) for x in data])


@router.get(
    "/cases/{case_id}/persons/{person_id}/portrait",
    response_model=ApiResponse[PersonPortraitOut],
)
def get_person_portrait(
    request: Request,
    case_id: int,
    person_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    neo4j_driver: Driver = Depends(get_neo4j_driver),
    minio: Minio = Depends(get_minio),
):
    """
    人物画像：经济 / 轨迹 / 社会关系子图 / 线索列表（一人一张图）。
    """
    data = portrait_service.get_person_portrait(
        db,
        neo4j_driver,
        minio,
        user=current_user,
        case_id=case_id,
        person_id=person_id,
    )
    audit_service.record(
        db,
        request,
        current_user,
        action="query_person_portrait",
        resource_type="person",
        resource_id=person_id,
        case_id=case_id,
    )
    return success_for_request(request, data)


@router.get("/clues/{clue_id}", response_model=ApiResponse[ClueDetailOut])
def get_clue(
    request: Request,
    clue_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    raw = clue_service.get_clue_detail(db, user=current_user, clue_id=clue_id)
    audit_service.record(
        db,
        request,
        current_user,
        action="query_clue_detail",
        resource_type="clue",
        resource_id=str(clue_id),
        case_id=raw.get("case_id"),
    )
    return success_for_request(request, ClueDetailOut.model_validate(raw))
