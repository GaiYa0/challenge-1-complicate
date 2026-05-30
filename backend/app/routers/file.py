"""
API 层 —— 文件路由
职责：只处理 HTTP；对象存储由 file_service → storage_service → infra/minio_client。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File as FastAPIFile, Query, Request, UploadFile
from minio import Minio
from redis import Redis
from sqlalchemy.orm import Session

from backend.app.routers.deps import get_current_user
from backend.core.deps import get_db, get_minio, get_redis
from backend.model.models import User
from backend.app.schemas.common import ApiResponse, success_for_request
from backend.app.schemas.file import (
    AnomalyData,
    CleanData,
    CleanRowsData,
    ColumnStats,
    FileDetailItem,
    FieldMappingConfirmIn,
    FieldMappingConfirmOut,
    FileUploadData,
    PreviewData,
)
from backend.app.services import data_pipeline_service, file_service
from backend.infra.redis_client import invalidate_analyze_for_file

router = APIRouter()


@router.post("/upload", response_model=ApiResponse[FileUploadData])
async def upload(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    minio: Minio = Depends(get_minio),
    file: UploadFile = FastAPIFile(...),
    dataset: str = Query("default", min_length=1, max_length=256),
    version: str = Query("v1", min_length=1, max_length=64),
):
    content = await file.read()
    data = file_service.upload_file(
        db, minio, redis, current_user, file.filename or "", content, dataset=dataset, version=version
    )
    return success_for_request(request, data)


@router.get("/files", response_model=ApiResponse[list[str]])
def list_files(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    data = file_service.list_filenames(db, redis, current_user)
    return success_for_request(request, data)


@router.get("/db/files", response_model=ApiResponse[list[FileDetailItem]])
def db_list_files(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    minio: Minio = Depends(get_minio),
):
    data = file_service.list_files_detail(db, minio, current_user)
    return success_for_request(request, data)


@router.delete("/db/file/{id}", response_model=ApiResponse[None])
def db_delete_file(
    request: Request,
    id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    minio: Minio = Depends(get_minio),
    redis: Redis = Depends(get_redis),
):
    file_service.delete_file_by_id(db, minio, redis, id, current_user)
    return success_for_request(request, None, msg="deleted")


@router.delete("/file/{filename}", response_model=ApiResponse[None])
def delete_file(
    request: Request,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    minio: Minio = Depends(get_minio),
    redis: Redis = Depends(get_redis),
):
    file_service.delete_file_by_name(db, minio, redis, filename, current_user)
    return success_for_request(request, None, msg="deleted")


@router.get("/preview/{filename}", response_model=ApiResponse[PreviewData])
def preview_csv(
    request: Request,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    minio: Minio = Depends(get_minio),
    redis: Redis = Depends(get_redis),
):
    data = file_service.preview_csv(db, minio, redis, filename, current_user)
    return success_for_request(request, data)


@router.get("/clean/{filename}", response_model=ApiResponse[CleanData])
def clean_csv(
    request: Request,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    minio: Minio = Depends(get_minio),
):
    data = file_service.clean_csv(db, minio, filename, current_user)
    return success_for_request(request, data)


@router.get("/clean/rows/{filename}", response_model=ApiResponse[CleanRowsData])
def clean_rows_csv(
    request: Request,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    minio: Minio = Depends(get_minio),
    redis: Redis = Depends(get_redis),
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
):
    data = file_service.clean_rows_csv(
        db, minio, filename, current_user, offset=offset, limit=limit, redis=redis
    )
    return success_for_request(request, data)


@router.get("/stats/{filename}", response_model=ApiResponse[dict[str, ColumnStats]])
def stats_csv(
    request: Request,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    minio: Minio = Depends(get_minio),
    redis: Redis = Depends(get_redis),
):
    data = file_service.stats_csv(db, minio, redis, filename, current_user)
    return success_for_request(request, data)


@router.get("/anomaly/{filename}", response_model=ApiResponse[AnomalyData])
def anomaly_csv(
    request: Request,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    minio: Minio = Depends(get_minio),
    redis: Redis = Depends(get_redis),
):
    data = file_service.anomaly_csv(db, minio, redis, filename, current_user)
    return success_for_request(request, data)


@router.post("/mapping/confirm", response_model=ApiResponse[FieldMappingConfirmOut])
def confirm_mapping(
    body: FieldMappingConfirmIn,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    minio: Minio = Depends(get_minio),
    redis: Redis = Depends(get_redis),
):
    data = data_pipeline_service.confirm_field_mapping(
        db,
        minio,
        filename=body.filename,
        user_id=int(current_user.id),
        mapping=body.mapping,
    )
    invalidate_analyze_for_file(redis, int(current_user.id), body.filename)
    return success_for_request(request, data)
