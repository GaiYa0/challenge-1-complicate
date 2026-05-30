from __future__ import annotations

from typing import Any

import pandas as pd
from minio import Minio
from sqlalchemy.orm import Session

from backend.app.repositories import file_repo
from backend.app.services.file_service import read_tabular_bytes_to_dataframe
from backend.data_platform.call_record_analysis_engine import analyze_call_records
from backend.data_platform.fund_flow_anomaly_engine import analyze_fund_flow
from backend.data_platform.multi_source_collision_engine import run_multi_source_collision
from backend.data_platform.person_profile_system import build_person_profile
from backend.data_platform.trajectory_anomaly_engine import analyze_trajectory
from backend.infra import minio_client as minio_ops

_FUND_FROM_KEYS = (
    "from_account",
    "name",
    "用户侧账号名称",
    "账号",
    "账户",
    "付款方",
    "payer",
)
_FUND_TO_KEYS = (
    "to_account",
    "counterparty",
    "对手侧账户名称",
    "对手方",
    "收款方",
    "payee",
)
_FUND_AMOUNT_KEYS = ("amount", "金额", "交易金额", "发生金额", "money")
_FUND_TIME_KEYS = ("txn_time", "交易时间", "时间", "timestamp", "date")

_CALL_CALLER_KEYS = ("caller", "主叫", "主叫号码", "from_phone", "from")
_CALL_CALLEE_KEYS = ("callee", "被叫", "被叫号码", "to_phone", "to")
_CALL_TIME_KEYS = ("call_time", "通话时间", "时间", "timestamp")

_TRIP_PERSON_KEYS = ("person_id", "name", "人员", "账号", "user")
_TRIP_TIME_KEYS = ("timestamp", "时间", "定位时间", "date_time")
_TRIP_LAT_KEYS = ("lat", "latitude", "纬度")
_TRIP_LNG_KEYS = ("lng", "lon", "longitude", "经度")


def _norm_col(col: object) -> str:
    return str(col).strip().lower()


def _pick_col(df: pd.DataFrame, keys: tuple[str, ...]) -> str | None:
    mapping = {_norm_col(c): str(c) for c in df.columns}
    for k in keys:
        if _norm_col(k) in mapping:
            return mapping[_norm_col(k)]
    for c in df.columns:
        ck = _norm_col(c)
        for k in keys:
            if _norm_col(k) in ck:
                return str(c)
    return None


def _clean_id_series(s: pd.Series) -> pd.Series:
    out = s.astype(str).str.strip()
    return out.where(~out.str.lower().isin(["", "nan", "none", "null"]), "")


def _read_case_tabular_dfs(
    db: Session,
    minio: Minio,
    *,
    tenant_user_id: int,
    case_id: int,
) -> list[pd.DataFrame]:
    out: list[pd.DataFrame] = []
    files = file_repo.list_tabular_files_for_case_dataset(
        db, tenant_user_id=tenant_user_id, case_id=case_id
    )
    for f in files:
        try:
            raw = minio_ops.get_bytes(minio, f.bucket_name, f.object_name)
            out.append(read_tabular_bytes_to_dataframe(f.filename or "", raw))
        except Exception:
            continue
    return out


def _fund_frame_from_df(df: pd.DataFrame) -> pd.DataFrame | None:
    c_from = _pick_col(df, _FUND_FROM_KEYS)
    c_to = _pick_col(df, _FUND_TO_KEYS)
    c_amt = _pick_col(df, _FUND_AMOUNT_KEYS)
    c_time = _pick_col(df, _FUND_TIME_KEYS)
    if not c_from or not c_to or not c_amt:
        return None
    out = pd.DataFrame()
    out["from_account"] = _clean_id_series(df[c_from])
    out["to_account"] = _clean_id_series(df[c_to])
    out["amount"] = pd.to_numeric(df[c_amt], errors="coerce")
    if c_time:
        out["txn_time"] = pd.to_datetime(df[c_time], errors="coerce", format="mixed")
    else:
        out["txn_time"] = pd.NaT
    out = out.dropna(subset=["amount"])
    out = out[
        (out["from_account"] != "")
        & (out["to_account"] != "")
        & (out["from_account"] != out["to_account"])
    ]
    return out if not out.empty else None


def _call_frame_from_df(df: pd.DataFrame) -> pd.DataFrame | None:
    c1 = _pick_col(df, _CALL_CALLER_KEYS)
    c2 = _pick_col(df, _CALL_CALLEE_KEYS)
    ct = _pick_col(df, _CALL_TIME_KEYS)
    if not c1 or not c2 or not ct:
        return None
    out = pd.DataFrame()
    out["caller"] = _clean_id_series(df[c1])
    out["callee"] = _clean_id_series(df[c2])
    out["call_time"] = pd.to_datetime(df[ct], errors="coerce", format="mixed")
    out = out.dropna(subset=["call_time"])
    out = out[(out["caller"] != "") & (out["callee"] != "") & (out["caller"] != out["callee"])]
    return out if not out.empty else None


def _trip_frame_from_df(df: pd.DataFrame) -> pd.DataFrame | None:
    cp = _pick_col(df, _TRIP_PERSON_KEYS)
    ct = _pick_col(df, _TRIP_TIME_KEYS)
    cla = _pick_col(df, _TRIP_LAT_KEYS)
    clo = _pick_col(df, _TRIP_LNG_KEYS)
    if not cp or not ct or not cla or not clo:
        return None
    out = pd.DataFrame()
    out["person_id"] = _clean_id_series(df[cp])
    out["timestamp"] = pd.to_datetime(df[ct], errors="coerce", format="mixed")
    out["lat"] = pd.to_numeric(df[cla], errors="coerce")
    out["lng"] = pd.to_numeric(df[clo], errors="coerce")
    out = out.dropna(subset=["timestamp", "lat", "lng"])
    out = out[(out["person_id"] != "")]
    return out if not out.empty else None


def build_case_frames(
    db: Session,
    minio: Minio,
    *,
    tenant_user_id: int,
    case_id: int,
) -> dict[str, Any]:
    dfs = _read_case_tabular_dfs(
        db, minio, tenant_user_id=tenant_user_id, case_id=case_id
    )
    fund_frames: list[pd.DataFrame] = []
    call_frames: list[pd.DataFrame] = []
    trip_frames: list[pd.DataFrame] = []
    for df in dfs:
        f = _fund_frame_from_df(df)
        if f is not None:
            fund_frames.append(f)
        c = _call_frame_from_df(df)
        if c is not None:
            call_frames.append(c)
        t = _trip_frame_from_df(df)
        if t is not None:
            trip_frames.append(t)

    fund_df = pd.concat(fund_frames, ignore_index=True) if fund_frames else pd.DataFrame(
        columns=["from_account", "to_account", "amount", "txn_time"]
    )
    call_df = pd.concat(call_frames, ignore_index=True) if call_frames else pd.DataFrame(
        columns=["caller", "callee", "call_time"]
    )
    trip_df = pd.concat(trip_frames, ignore_index=True) if trip_frames else pd.DataFrame(
        columns=["person_id", "timestamp", "lat", "lng"]
    )

    persons: set[str] = set()
    if not fund_df.empty:
        persons |= set(fund_df["from_account"].astype(str).tolist())
        persons |= set(fund_df["to_account"].astype(str).tolist())
    if not call_df.empty:
        persons |= set(call_df["caller"].astype(str).tolist())
        persons |= set(call_df["callee"].astype(str).tolist())
    if not trip_df.empty:
        persons |= set(trip_df["person_id"].astype(str).tolist())
    persons.discard("")

    return {
        "fund_df": fund_df,
        "call_df": call_df,
        "trip_df": trip_df,
        "persons": persons,
    }


def run_case_analytics(
    db: Session,
    minio: Minio,
    *,
    tenant_user_id: int,
    case_id: int,
) -> dict[str, Any]:
    frames = build_case_frames(
        db, minio, tenant_user_id=tenant_user_id, case_id=case_id
    )
    fund_df: pd.DataFrame = frames["fund_df"]
    call_df: pd.DataFrame = frames["call_df"]
    trip_df: pd.DataFrame = frames["trip_df"]
    fund_result = analyze_fund_flow(fund_df) if not fund_df.empty else {"anomalies": [], "graph_data": {"nodes": [], "edges": []}}
    call_result = analyze_call_records(call_df) if not call_df.empty else {"night_call_ratio": 0.0, "top_contacts": [], "central_nodes": []}
    trajectory_result = analyze_trajectory(trip_df, sensitive_points=[]) if not trip_df.empty else {"suspicious_trips": [], "co_occurrence": []}
    collision_result = run_multi_source_collision(
        fund_result=fund_result,
        call_result=call_result,
        trajectory_result=trajectory_result,
        call_df=call_df if not call_df.empty else None,
        trajectory_df=trip_df if not trip_df.empty else None,
        extra_person_ids=frames["persons"],
    )
    return {
        **frames,
        "fund_result": fund_result,
        "call_result": call_result,
        "trajectory_result": trajectory_result,
        "collision_result": collision_result,
    }


def build_person_profile_from_case_analytics(
    person_id: str,
    analytics: dict[str, Any],
) -> dict[str, Any]:
    return build_person_profile(
        person_id,
        fund_result=analytics.get("fund_result"),
        call_result=analytics.get("call_result"),
        trajectory_result=analytics.get("trajectory_result"),
        collision_events=(analytics.get("collision_result") or {}).get("events") or [],
        basic_info={"name": person_id},
    )
