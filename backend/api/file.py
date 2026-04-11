"""
API 层 —— 文件路由
职责：只处理 HTTP；对象存储由 file_service → storage_service → infra/minio_client。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File as FastAPIFile, Query, Request, UploadFile
from minio import Minio
from redis import Redis
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.core.deps import get_db, get_minio, get_redis
from backend.model.models import User
from backend.schema.common import ApiResponse, success_for_request
from backend.schema.file import (
    AnomalyData,
    CleanData,
    ColumnStats,
    FileDetailItem,
    FileUploadData,
    PreviewData,
)
from backend.service import file_service

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
