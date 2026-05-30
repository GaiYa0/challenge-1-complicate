"""
Repository 层 —— 文件数据访问（多租户：默认必须带 user_id 条件；仅 *_all 系列供 admin 显式调用）。
"""

from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from backend.model.enums import DataLayer
from backend.model.models import File


def insert_file(
    db: Session,
    *,
    user_id: int,
    filename: str,
    bucket_name: str,
    object_name: str,
    version: str,
    dataset: str,
    data_layer: str = DataLayer.RAW.value,
) -> File:
    warm_month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    rec = File(
        user_id=user_id,
        filename=filename,
        bucket_name=bucket_name,
        object_name=object_name,
        version=version,
        dataset=dataset,
        data_layer=data_layer,
        lifecycle_tier="hot",
        warm_month_key=warm_month_key,
    )
    db.add(rec)
    db.flush()
    return rec


def list_filenames_for_tenant(db: Session, *, tenant_user_id: int) -> list[str]:
    q = (
        select(File.filename)
        .where(File.user_id == tenant_user_id)
        .order_by(File.filename)
    )
    return list(db.execute(q).scalars().all())


def list_filenames_all(db: Session) -> list[str]:
    """仅管理员场景：全库文件名（无租户过滤）。"""
    q = select(File.filename).order_by(File.filename)
    return list(db.execute(q).scalars().all())


def list_files_for_tenant(db: Session, *, tenant_user_id: int) -> list[File]:
    q = (
        select(File)
        .where(File.user_id == tenant_user_id)
        .order_by(File.created_at.desc(), File.id)
    )
    return list(db.execute(q).scalars().all())


def list_tabular_files_for_case_dataset(
    db: Session, *, tenant_user_id: int, case_id: int
) -> list[File]:
    """案件专属 dataset（如 case-8）下的结构化文件，排除特征衍生文件。"""
    ds = f"case-{int(case_id)}"
    q = (
        select(File)
        .where(File.user_id == tenant_user_id, File.dataset == ds)
        .order_by(File.created_at.asc(), File.id)
    )
    rows = list(db.execute(q).scalars().all())
    out: list[File] = []
    for f in rows:
        fn = (f.filename or "").lower()
        if not (
            fn.endswith(".csv")
            or fn.endswith(".xls")
            or fn.endswith(".xlsx")
            or fn.endswith(".txt")
            or fn.endswith(".json")
        ):
            continue
        base = f.filename or ""
        if base.startswith("feature_"):
            continue
        out.append(f)
    return out


def list_csv_files_for_case_dataset(
    db: Session, *, tenant_user_id: int, case_id: int
) -> list[File]:
    """兼容旧名，等价于 list_tabular_files_for_case_dataset。"""
    return list_tabular_files_for_case_dataset(db, tenant_user_id=tenant_user_id, case_id=case_id)


def list_files_all(db: Session) -> list[File]:
    """仅管理员场景。"""
    q = select(File).order_by(File.created_at.desc(), File.id)
    return list(db.execute(q).scalars().all())


def get_file_for_tenant(db: Session, filename: str, tenant_user_id: int) -> File | None:
    """普通用户：必须 WHERE user_id = tenant_user_id。"""
    return db.scalars(
        select(File).where(File.filename == filename, File.user_id == tenant_user_id).limit(1)
    ).first()


def list_files_by_filename_all_tenants(db: Session, filename: str) -> list[File]:
    """管理员排障：按文件名跨租户列出（可能多条，用于歧义检测）。"""
    return list(db.scalars(select(File).where(File.filename == filename)).all())


def get_file_by_id_for_tenant(db: Session, file_id: int, tenant_user_id: int) -> File | None:
    return db.scalars(
        select(File).where(File.id == file_id, File.user_id == tenant_user_id).limit(1)
    ).first()


def get_file_by_id_any(db: Session, file_id: int) -> File | None:
    """仅管理员场景：按主键取行（无 user_id 条件）。"""
    return db.get(File, file_id)


def delete_file_by_id(db: Session, file_id: int) -> None:
    rec = db.get(File, file_id)
    if rec:
        db.delete(rec)
        db.flush()


def delete_file_for_tenant_by_name(db: Session, filename: str, tenant_user_id: int) -> None:
    db.execute(delete(File).where(File.filename == filename, File.user_id == tenant_user_id))
    db.flush()


def bulk_set_tier_warm_before(db: Session, *, created_before) -> list[int]:
    """将早于阈值的 hot 行降为 warm，返回受影响的 file id 列表。"""
    q = (
        select(File.id)
        .where(File.lifecycle_tier == "hot", File.created_at < created_before)
        .limit(5000)
    )
    ids = [int(x) for x in db.execute(q).scalars().all()]
    if not ids:
        return []
    db.execute(update(File).where(File.id.in_(ids)).values(lifecycle_tier="warm"))
    db.flush()
    return ids


def list_warm_files_older_than(db: Session, *, created_before, limit: int = 50) -> list[File]:
    return list(
        db.scalars(
            select(File)
            .where(File.lifecycle_tier == "warm", File.created_at < created_before)
            .order_by(File.created_at.asc())
            .limit(limit)
        ).all()
    )
