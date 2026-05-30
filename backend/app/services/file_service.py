"""
Service 层 —— 文件业务逻辑
职责：编排校验、统一存储、事务、Redis 读穿缓存（防击穿 + TTL 抖动）、失效。
"""

import json
import re
import time
from csv import Sniffer
from io import BytesIO

import numpy as np
import pandas as pd
from minio import Minio
from redis import Redis
from sqlalchemy.orm import Session

from backend.core.exceptions import ServiceError
from backend.core.perf_context import add_db_time_ms
from backend.core.tenant_access import is_admin, resolve_file_for_read
from backend.core.transaction import transaction
from backend.infra.redis_client import (
    analyze_cache_key,
    files_list_cache_key,
    invalidate_analyze_for_file,
    invalidate_files_list,
    read_through_json,
)
from backend.model.models import User
from backend.app.repositories import file_repo
from backend.app.schemas.file import (
    AnomalyData,
    CleanData,
    CleanRowItem,
    CleanRowsData,
    ColumnStats,
    FileDetailItem,
    FileUploadData,
    PreviewData,
)
from backend.core.config import get_settings
from backend.app.services import storage_service


def file_owner_user_id_if_accessible(
    db: Session, filename: str, user: User, *, dataset: str | None = None,
) -> int | None:
    try:
        return int(resolve_file_for_read(db, user, filename, dataset=dataset).user_id)
    except ServiceError:
        return None


def _cache_partition_user_id(db: Session, filename: str, user: User) -> int:
    """缓存键中的 user_id 段：按文件行属主分区，避免同名跨租户串缓存。"""
    return int(resolve_file_for_read(db, user, filename).user_id)


def read_csv_as_dataframe(db: Session, minio: Minio, filename: str, user: User) -> pd.DataFrame:
    """供分析 / 特征 / 模型等 Service 复用（支持 CSV / XLS / XLSX / TXT / JSON）。"""
    return _load_csv_df(db, minio, filename, user, redis=None)


_EXCEL_EXTS = (".xls", ".xlsx")
_XLS_MAGIC = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"
_ZIP_MAGIC = b"PK\x03\x04"
_CSV_DELIMS = (",", ";", "\t", "|", "，")
_INVISIBLE_CTRL_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060\ufeff]")
_HEADER_HINT_RE = re.compile(
    r"(name|title|header|column|time|date|amount|amt|id|no|code|type|字段|表头|类型|名称|账号|账户|编号|时间|日期|金额|地点|地址|备注|说明|状态)",
    re.IGNORECASE,
)
_COMMON_SURNAME_SET = set(
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计成戴宋庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯昝管卢莫房裘缪干解应宗丁宣贲邓郁单杭洪包诸左石崔吉钮龚程嵇邢滑裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘斜厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲台从鄂索咸籍赖卓蔺屠蒙池乔阴鬱胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍却璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公"
)


def _clean_header_token(value: object) -> str:
    text = str(value).strip()
    text = _INVISIBLE_CTRL_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def _decode_text(raw: bytes) -> str:
    for enc in ("utf-8", "gb18030", "gbk"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="ignore")


def _read_txt_table(raw: bytes) -> pd.DataFrame:
    text = _decode_text(raw)
    return _read_csv_like_text(text)


def _read_json_table(raw: bytes) -> pd.DataFrame:
    obj = json.loads(_decode_text(raw))
    if isinstance(obj, list):
        return pd.json_normalize(obj)
    if isinstance(obj, dict):
        if "items" in obj and isinstance(obj["items"], list):
            return pd.json_normalize(obj["items"])
        return pd.json_normalize([obj])
    raise ServiceError("JSON 内容不支持结构化解析")


def _flatten_column_name(col: object) -> str:
    if isinstance(col, tuple):
        parts = [
            _clean_header_token(x)
            for x in col
            if _clean_header_token(x) and _clean_header_token(x).lower() != "nan"
        ]
        return "_".join(parts) if parts else ""
    s = _clean_header_token(col)
    if s.lower() == "nan":
        return ""
    return s


def _sanitize_columns(cols: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out: list[str] = []
    for i, c in enumerate(cols):
        base = _clean_header_token(c or "")
        if not base:
            base = f"col_{i+1}"
        idx = seen.get(base, 0) + 1
        seen[base] = idx
        out.append(base if idx == 1 else f"{base}_{idx}")
    return out


def _normalize_table_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = [_flatten_column_name(c) for c in out.columns]
    else:
        out.columns = [_flatten_column_name(c) for c in out.columns]
    out.columns = _sanitize_columns([str(c) for c in out.columns])
    out = out.dropna(axis=0, how="all")
    out = out.dropna(axis=1, how="all")
    return out.reset_index(drop=True)


def _looks_like_header_row(row: pd.Series) -> bool:
    vals = [
        _clean_header_token(x)
        for x in row.tolist()
        if _clean_header_token(x) and _clean_header_token(x).lower() != "nan"
    ]
    if len(vals) < 2:
        return False
    text_like = sum(1 for v in vals if not re.fullmatch(r"[-+]?\d+(\.\d+)?", v))
    return text_like >= max(1, int(len(vals) * 0.5))


def _is_data_like_value(v: str) -> bool:
    if not v:
        return False
    vv = v.strip()
    if re.fullmatch(r"[-+]?\d+(\.\d+)?", vv):
        return True
    if re.fullmatch(r"\d{11,19}", vv):
        return True
    if re.fullmatch(r"\d{17}[\dXx]", vv):
        return True
    if re.search(r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}", vv):
        return True
    if re.search(r"\d{1,2}:\d{2}(:\d{2})?", vv):
        return True
    if re.fullmatch(r"[A-Za-z0-9_-]{8,}", vv):
        digit_count = sum(1 for ch in vv if ch.isdigit())
        if digit_count >= 4:
            return True
    return False


def _has_grouped_top_header_pattern(row1: pd.Series) -> bool:
    vals = [
        _clean_header_token(x)
        for x in row1.tolist()
        if _clean_header_token(x) and _clean_header_token(x).lower() != "nan"
    ]
    if len(vals) < 2:
        return False
    repeats = len(vals) - len(set(vals))
    return repeats >= max(1, int(len(vals) * 0.15))


def _likely_chinese_person_name(v: str) -> bool:
    vv = v.strip()
    if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", vv):
        return False
    return vv[0] in _COMMON_SURNAME_SET


def _should_use_second_header_row(row1: pd.Series, row2: pd.Series) -> bool:
    vals = [
        _clean_header_token(x)
        for x in row2.tolist()
        if _clean_header_token(x) and _clean_header_token(x).lower() != "nan"
    ]
    if len(vals) < 2:
        return False
    if not _looks_like_header_row(row2):
        return False
    data_like = sum(1 for v in vals if _is_data_like_value(v))
    if data_like >= max(2, int(len(vals) * 0.25)):
        return False
    header_like = sum(1 for v in vals if _HEADER_HINT_RE.search(v))
    grouped_top = _has_grouped_top_header_pattern(row1)
    if header_like >= max(1, int(len(vals) * 0.1)):
        return True
    if grouped_top:
        chinese_name_like = sum(1 for v in vals if _likely_chinese_person_name(v))
        if chinese_name_like >= max(2, int(len(vals) * 0.4)):
            return False
    return grouped_top


def _frame_from_raw_with_header_detection(df_raw: pd.DataFrame) -> pd.DataFrame:
    if df_raw is None or df_raw.empty:
        return pd.DataFrame()
    probe = df_raw.head(12)
    header_idx = None
    for i in range(len(probe)):
        if _looks_like_header_row(probe.iloc[i]):
            header_idx = i
            break
    if header_idx is None:
        return _normalize_table_df(df_raw)
    header_vals_1 = [_clean_header_token(x) for x in df_raw.iloc[header_idx].tolist()]
    header_vals_2: list[str] | None = None
    if header_idx + 1 < len(df_raw) and _should_use_second_header_row(
        df_raw.iloc[header_idx], df_raw.iloc[header_idx + 1]
    ):
        header_vals_2 = [_clean_header_token(x) for x in df_raw.iloc[header_idx + 1].tolist()]
    if header_vals_2:
        cols: list[str] = []
        for a, b in zip(header_vals_1, header_vals_2):
            aa = "" if a.lower() == "nan" else a
            bb = "" if b.lower() == "nan" else b
            merged = "_".join([x for x in [aa, bb] if x]).strip("_")
            cols.append(merged)
        body = df_raw.iloc[header_idx + 2 :].copy()
        body.columns = _sanitize_columns(cols)
        return _normalize_table_df(body)
    body = df_raw.iloc[header_idx + 1 :].copy()
    body.columns = _sanitize_columns(
        ["" if str(x).strip().lower() == "nan" else str(x).strip() for x in header_vals_1]
    )
    return _normalize_table_df(body)


def _choose_best_sheet(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    best: pd.DataFrame | None = None
    best_score = -1
    for _, fr in frames.items():
        cand = _frame_from_raw_with_header_detection(fr)
        if cand.empty:
            continue
        score = int(cand.shape[0]) * 2 + int(cand.shape[1])
        if score > best_score:
            best_score = score
            best = cand
    return best if best is not None else pd.DataFrame()


def _read_csv_like_text(text: str) -> pd.DataFrame:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln for ln in text.split("\n") if ln.strip()]
    if not lines:
        return pd.DataFrame()
    sample = "\n".join(lines[:20])
    delimiter = None
    try:
        dialect = Sniffer().sniff(sample, delimiters="".join(_CSV_DELIMS))
        delimiter = dialect.delimiter
    except Exception:
        delimiter = None
    if delimiter:
        try:
            df = pd.read_csv(BytesIO("\n".join(lines).encode("utf-8")), sep=delimiter, engine="python")
            return _normalize_table_df(df)
        except Exception:
            pass
    try:
        df = pd.read_csv(BytesIO("\n".join(lines).encode("utf-8")), sep=None, engine="python")
        return _normalize_table_df(df)
    except Exception:
        rows = []
        for ln in lines:
            parts = re.split(r"[,\t;|，]+", ln.strip())
            if len(parts) > 1:
                rows.append(parts)
        if rows:
            width = max(len(r) for r in rows)
            norm_rows = [r + [""] * (width - len(r)) for r in rows]
            df = pd.DataFrame(norm_rows)
            return _frame_from_raw_with_header_detection(df)
        return pd.DataFrame([{"text": ln.strip()} for ln in lines if ln.strip()])


def _read_excel_with_fallback(filename: str, raw: bytes) -> pd.DataFrame:
    lower = filename.lower()
    engine = "xlrd" if lower.endswith(".xls") else "openpyxl"
    try:
        all_sheets = pd.read_excel(BytesIO(raw), engine=engine, sheet_name=None, header=None)
        out = _choose_best_sheet(all_sheets)
        if out.empty:
            return pd.DataFrame()
        return out
    except Exception as exc:
        # 扩展名与内容不一致时（如 .xls 实际是文本/CSV），降级为文本解析，避免任务链路连锁失败。
        is_binary_excel = raw.startswith(_XLS_MAGIC) or raw.startswith(_ZIP_MAGIC)
        if is_binary_excel:
            raise ServiceError(f"Excel 解析失败: {exc}") from exc
        text = _decode_text(raw)
        return _read_csv_like_text(text)


def read_tabular_bytes_to_dataframe(filename: str, raw: bytes) -> pd.DataFrame:
    """
    按扩展名从字节加载表格（与 _load_csv_df 规则一致），供构图等仅持有 bytes 的场景复用。
    """
    lower = filename.lower()
    if lower.endswith(".csv"):
        text = _decode_text(raw)
        return _read_csv_like_text(text)
    if lower.endswith(".xls") or lower.endswith(".xlsx"):
        return _read_excel_with_fallback(filename, raw)
    if lower.endswith(".txt"):
        return _read_txt_table(raw)
    if lower.endswith(".json"):
        return _normalize_table_df(_read_json_table(raw))
    raise ServiceError("仅支持 CSV / XLS / XLSX / TXT / JSON 格式")


def _load_csv_df(
    db: Session,
    minio: Minio,
    filename: str,
    user: User,
    *,
    redis: Redis | None,
) -> pd.DataFrame:
    resolve_file_for_read(db, user, filename)
    lower = filename.lower()
    if not (
        lower.endswith(".csv")
        or lower.endswith(".xls")
        or lower.endswith(".xlsx")
        or lower.endswith(".txt")
        or lower.endswith(".json")
    ):
        raise ServiceError("仅支持 CSV / XLS / XLSX / TXT / JSON 格式")
    t0 = time.perf_counter()
    try:
        raw = storage_service.read_file_bytes(db, minio, filename, user, redis=redis)
        return read_tabular_bytes_to_dataframe(filename, raw)
    finally:
        add_db_time_ms((time.perf_counter() - t0) * 1000.0)


# ── 上传 ────────────────────────────────────────────

def upload_file(
    db: Session,
    minio: Minio,
    redis: Redis,
    user: User,
    raw_filename: str,
    content: bytes,
    *,
    dataset: str = "default",
    version: str = "v1",
) -> FileUploadData:
    out = storage_service.save_file(
        db, minio, user, raw_filename, content, dataset=dataset, version=version
    )
    invalidate_files_list(redis, user.id)
    invalidate_analyze_for_file(redis, user.id, out.filename)
    settings = get_settings()
    if settings.KAFKA_ENABLED:
        from backend.events.producer import publish_data_uploaded

        publish_data_uploaded(user.id, out.filename)
    elif settings.KAFKA_UPLOAD_FALLBACK_CELERY:
        from backend.tasks.clean_task import clean_data_task

        clean_data_task.delay(out.filename, user.id)
    return out


# ── 列表 ────────────────────────────────────────────

def list_filenames(db: Session, redis: Redis, user: User) -> list[str]:
    if is_admin(user):
        t0 = time.perf_counter()
        try:
            return file_repo.list_filenames_all(db)
        finally:
            add_db_time_ms((time.perf_counter() - t0) * 1000.0)

    uid = user.id
    key = files_list_cache_key(uid)

    def _compute() -> dict:
        t0 = time.perf_counter()
        try:
            names = file_repo.list_filenames_for_tenant(db, tenant_user_id=uid)
        finally:
            add_db_time_ms((time.perf_counter() - t0) * 1000.0)
        return {"items": names}

    return read_through_json(redis, key, _compute, base_ttl=120, jitter_max=40)["items"]


def list_files_detail(db: Session, minio: Minio, user: User) -> list[FileDetailItem]:
    t0 = time.perf_counter()
    try:
        if is_admin(user):
            rows = file_repo.list_files_all(db)
        else:
            rows = file_repo.list_files_for_tenant(db, tenant_user_id=user.id)
    finally:
        add_db_time_ms((time.perf_counter() - t0) * 1000.0)
    items: list[FileDetailItem] = []
    for r in rows:
        url = storage_service.presigned_for_row(minio, r)
        items.append(
            FileDetailItem(
                filename=r.filename,
                bucket_name=r.bucket_name,
                object_name=r.object_name,
                version=r.version,
                dataset=r.dataset,
                data_layer=r.data_layer,
                upload_time=r.created_at.isoformat() if r.created_at else None,
                presigned_url=url,
                lifecycle_tier=getattr(r, "lifecycle_tier", None),
                archive_format=getattr(r, "archive_format", None),
                warm_month_key=getattr(r, "warm_month_key", None),
            )
        )
    return items


# ── 删除（按 ID）────────────────────────────────────

def delete_file_by_id(db: Session, minio: Minio, redis: Redis, file_id: int, user: User) -> None:
    if is_admin(user):
        rec = file_repo.get_file_by_id_any(db, file_id)
    else:
        rec = file_repo.get_file_by_id_for_tenant(db, file_id, user.id)
    if rec is None:
        raise ServiceError("not found")
    try:
        with transaction(db):
            file_repo.delete_file_by_id(db, file_id)
    except Exception:
        raise
    storage_service.delete_object_for_row(minio, rec)
    invalidate_analyze_for_file(redis, rec.user_id, rec.filename)
    invalidate_files_list(redis, rec.user_id)


# ── 删除（按文件名）──────────────────────────────────

def delete_file_by_name(db: Session, minio: Minio, redis: Redis, filename: str, user: User) -> None:
    if is_admin(user):
        rows = file_repo.list_files_by_filename_all_tenants(db, filename)
        own = [r for r in rows if r.user_id == user.id]
        if own:
            rows = own
        if not rows:
            raise ServiceError("file not found")
        rec = rows[0]
    else:
        rec = file_repo.get_file_for_tenant(db, filename, user.id)
        if rec is None:
            raise ServiceError("file not found")
    if is_admin(user):
        try:
            with transaction(db):
                file_repo.delete_file_by_id(db, rec.id)
        except Exception:
            raise
    else:
        try:
            with transaction(db):
                file_repo.delete_file_for_tenant_by_name(db, filename, user.id)
        except Exception:
            raise
    storage_service.delete_object_for_row(minio, rec)
    invalidate_analyze_for_file(redis, rec.user_id, rec.filename)
    invalidate_files_list(redis, rec.user_id)


# ── CSV 预览 ─────────────────────────────────────────

def preview_csv(db: Session, minio: Minio, redis: Redis, filename: str, user: User) -> PreviewData:
    part_uid = _cache_partition_user_id(db, filename, user)
    key = analyze_cache_key("preview", part_uid, filename)

    def _compute() -> dict:
        df = _load_csv_df(db, minio, filename, user, redis=redis)
        rows = json.loads(df.head(5).to_json(orient="records", date_format="iso"))
        dtypes = {str(c): str(t) for c, t in df.dtypes.items()}
        return PreviewData(
            columns=df.columns.tolist(),
            dtypes=dtypes,
            shape=[int(df.shape[0]), int(df.shape[1])],
            preview=rows,
        ).model_dump(mode="json")

    data = read_through_json(redis, key, _compute)
    return PreviewData.model_validate(data)


# ── 清洗 ────────────────────────────────────────────

def clean_csv(db: Session, minio: Minio, filename: str, user: User) -> CleanData:
    df = _load_csv_df(db, minio, filename, user, redis=None)
    before = int(len(df))
    cleaned = df.dropna()
    after = int(len(cleaned))
    return CleanData(before=before, after=after)


def _anomaly_mask_numeric(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=bool)
    num_df = df.select_dtypes(include=[np.integer, np.floating])
    if num_df.empty:
        return pd.Series(False, index=df.index)
    mask = pd.Series(False, index=df.index)
    for col in num_df.columns:
        s = num_df[col]
        m, st = s.mean(), s.std()
        if pd.isna(m) or pd.isna(st) or st == 0:
            continue
        lower = float(m) - 2 * float(st)
        upper = float(m) + 2 * float(st)
        bad = s.notna() & ((s < lower) | (s > upper))
        mask = mask | bad
    return mask


def clean_rows_csv(
    db: Session,
    minio: Minio,
    filename: str,
    user: User,
    *,
    offset: int = 0,
    limit: int = 200,
    redis: Redis | None = None,
) -> CleanRowsData:
    from backend.app.services import data_pipeline_service

    safe_offset = max(0, int(offset))
    safe_limit = max(1, min(int(limit), 500))

    owner_id = file_owner_user_id_if_accessible(db, filename, user)
    if owner_id is None:
        raise ServiceError("file not found")

    def _compute() -> dict:
        df_raw = data_pipeline_service.read_user_csv_dataframe(
            db, minio, filename=filename, user_id=owner_id
        )
        # 只读详情查询不应触发映射学习写入，避免 GET 产生副作用。
        df_clean, clean_meta = data_pipeline_service.standard_clean(
            db, df_raw, user_id=owner_id, filename=filename, persist_mapping=False
        )
        total = int(len(df_clean))
        if total == 0:
            return CleanRowsData(
                rows=[],
                total=0,
                offset=safe_offset,
                limit=safe_limit,
                rows_before=int(clean_meta.get("rows_before") or 0),
                rows_after=int(clean_meta.get("rows_after") or 0),
            ).model_dump(mode="json")

        anomaly_mask = _anomaly_mask_numeric(df_clean).reindex(df_clean.index, fill_value=False)
        pending_mask = pd.Series(False, index=df_clean.index)
        pending_candidates = df_clean.index[~anomaly_mask][:5]
        if len(pending_candidates):
            pending_mask.loc[pending_candidates] = True

        page = df_clean.iloc[safe_offset : safe_offset + safe_limit]
        page_records = json.loads(page.to_json(orient="records", date_format="iso"))
        rows: list[CleanRowItem] = []
        for i, data in enumerate(page_records):
            global_idx = safe_offset + i
            if global_idx >= total:
                break
            row_idx = df_clean.index[global_idx]
            status = "normal"
            if bool(anomaly_mask.loc[row_idx]):
                status = "anomaly"
            elif bool(pending_mask.loc[row_idx]):
                status = "pending"
            rows.append(
                CleanRowItem(
                    index=global_idx + 1,
                    status=status,
                    data=data,
                )
            )

        return CleanRowsData(
            rows=rows,
            total=total,
            offset=safe_offset,
            limit=safe_limit,
            rows_before=int(clean_meta.get("rows_before") or len(df_raw)),
            rows_after=int(clean_meta.get("rows_after") or len(df_clean)),
        ).model_dump(mode="json")

    if redis is not None and safe_offset == 0 and safe_limit == 200:
        part_uid = _cache_partition_user_id(db, filename, user)
        key = analyze_cache_key("clean_rows", part_uid, filename)
        payload = read_through_json(redis, key, _compute, base_ttl=60, jitter_max=20)
        return CleanRowsData.model_validate(payload)

    return CleanRowsData.model_validate(_compute())


# ── 统计 ────────────────────────────────────────────

def stats_csv(db: Session, minio: Minio, redis: Redis, filename: str, user: User) -> dict[str, ColumnStats]:
    part_uid = _cache_partition_user_id(db, filename, user)
    key = analyze_cache_key("stats", part_uid, filename)

    def _compute() -> dict:
        df = _load_csv_df(db, minio, filename, user, redis=redis)
        num_df = df.select_dtypes(include=[np.integer, np.floating])

        def _v(v):
            return None if pd.isna(v) else float(v)

        result: dict[str, ColumnStats] = {}
        for col in num_df.columns:
            s = num_df[col]
            result[str(col)] = ColumnStats(mean=_v(s.mean()), max=_v(s.max()), min=_v(s.min()))
        return {k: v.model_dump() for k, v in result.items()}

    raw = read_through_json(redis, key, _compute)
    return {k: ColumnStats.model_validate(v) for k, v in raw.items()}


# ── 异常检测 ─────────────────────────────────────────

def anomaly_csv(db: Session, minio: Minio, redis: Redis, filename: str, user: User) -> AnomalyData:
    part_uid = _cache_partition_user_id(db, filename, user)
    key = analyze_cache_key("anomaly", part_uid, filename)

    def _compute() -> dict:
        df = _load_csv_df(db, minio, filename, user, redis=redis)
        num_df = df.select_dtypes(include=[np.integer, np.floating])
        anomaly_count = 0
        for col in num_df.columns:
            s = num_df[col]
            m, st = s.mean(), s.std()
            if pd.isna(m) or pd.isna(st) or st == 0:
                continue
            lower = float(m) - 2 * float(st)
            upper = float(m) + 2 * float(st)
            bad = s.notna() & ((s < lower) | (s > upper))
            anomaly_count += int(bad.sum())
        return AnomalyData(anomaly_count=anomaly_count).model_dump()

    return AnomalyData.model_validate(read_through_json(redis, key, _compute))
