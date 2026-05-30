from __future__ import annotations

import hashlib

from minio import Minio
from neo4j import Driver
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.core.exceptions import AppError, ForbiddenError
from backend.core.tenant_access import is_admin
from backend.data_platform.call_record_analysis_engine import analyze_call_records
from backend.data_platform.risk_scoring_system import classify_risk_level
from backend.model.clue import Clue
from backend.model.clue_enums import ClueCategory, ClueRiskLevel
from backend.model.models import User
from backend.app.repositories import case_repo, clue_repo, file_repo
from backend.app.services import case_graph_service, case_intel_service, graph_service, tabular_graph_adapter


def _ensure_case_owned(db: Session, user: User, case_id: int):
    row = case_repo.get_by_id(db, case_id)
    if row is None:
        raise AppError("案件不存在", code=42001, status_code=404)
    if not is_admin(user) and row.user_id != user.id:
        raise ForbiddenError("无权访问该案件", code=42002)
    return row


def case_tabular_is_fund_table_only(db: Session, *, case_id: int, tenant_user_id: int) -> bool:
    """本案表格文件是否均为资金交易/注册信息类（按文件名启发式）。"""
    files = file_repo.list_tabular_files_for_case_dataset(
        db, tenant_user_id=tenant_user_id, case_id=case_id
    )
    if not files:
        return False
    for f in files:
        fn = f.filename or ""
        if not (
            tabular_graph_adapter.is_fund_trade_file_name(fn)
            or tabular_graph_adapter.is_registry_profile_file(fn)
        ):
            return False
    return True


def case_tabular_is_tenpay_only(db: Session, *, case_id: int, tenant_user_id: int) -> bool:
    """兼容旧函数名，语义已升级为通用资金类表判断。"""
    return case_tabular_is_fund_table_only(
        db,
        case_id=case_id,
        tenant_user_id=tenant_user_id,
    )


def _to_risk_level(level: str) -> ClueRiskLevel:
    lv = (level or "").strip().lower()
    if lv == "high":
        return ClueRiskLevel.high
    if lv == "medium":
        return ClueRiskLevel.medium
    return ClueRiskLevel.low


def _risk_prompts(level: str) -> list[dict[str, str]]:
    if level == "high":
        return [{"level": "high", "text": "建议优先核查并固定电子数据。"}]
    if level == "medium":
        return [{"level": "medium", "text": "建议结合更多证据进行交叉验证。"}]
    return [{"level": "low", "text": "当前风险较低，建议持续关注。"}]


def _build_real_clues_for_person(
    *,
    case_id: int,
    person_id: str,
    analytics: dict,
) -> list[Clue]:
    profile = case_intel_service.build_person_profile_from_case_analytics(person_id, analytics)
    risk_score = float(profile.get("risk_score") or 0.0)
    risk_level = str(profile.get("basic_info", {}).get("risk_level") or classify_risk_level(risk_score))
    rows: list[Clue] = []

    fund_anomalies = [
        a
        for a in (analytics.get("fund_result", {}).get("anomalies") or [])
        if str(a.get("from_account", "")) == person_id or str(a.get("to_account", "")) == person_id
    ]
    for a in fund_anomalies[:4]:
        sc = float(a.get("score") or risk_score)
        lv = classify_risk_level(sc)
        rows.append(
            Clue(
                case_id=case_id,
                person_id=person_id,
                title=f"资金异常：{a.get('type', 'fund')}",
                summary=f"命中资金异常规则，关联账户 {a.get('from_account', '')} -> {a.get('to_account', '')}。",
                category=ClueCategory.fund,
                risk_level=_to_risk_level(lv),
                risk_score=round(sc, 2),
                rule_hits=[str(a.get("type", "fund"))],
                feature_snapshot=a if isinstance(a, dict) else {},
                risk_prompts=_risk_prompts(lv),
            )
        )

    call_df = analytics.get("call_df")
    night_ratio = 0.0
    if isinstance(call_df, type(None)) or getattr(call_df, "empty", True):
        night_ratio = 0.0
    else:
        mask = (call_df["caller"].astype(str) == person_id) | (call_df["callee"].astype(str) == person_id)
        sub = call_df.loc[mask]
        if not sub.empty:
            night_ratio = float(analyze_call_records(sub).get("night_call_ratio") or 0.0)
    if night_ratio > 0:
        call_score = min(100.0, night_ratio * 100.0)
        call_lv = classify_risk_level(call_score)
        rows.append(
            Clue(
                case_id=case_id,
                person_id=person_id,
                title="通话行为异常",
                summary=f"夜间通话占比 {night_ratio:.0%}，需要结合案情复核。",
                category=ClueCategory.call,
                risk_level=_to_risk_level(call_lv),
                risk_score=round(call_score, 2),
                rule_hits=["night_call_ratio"],
                feature_snapshot={"night_call_ratio": night_ratio},
                risk_prompts=_risk_prompts(call_lv),
            )
        )

    trip_hits = [
        t for t in (analytics.get("trajectory_result", {}).get("suspicious_trips") or [])
        if str(t.get("person_id", "")) == person_id
    ]
    if trip_hits:
        trip_score = min(100.0, 40.0 + len(trip_hits) * 15.0)
        trip_lv = classify_risk_level(trip_score)
        rows.append(
            Clue(
                case_id=case_id,
                person_id=person_id,
                title="轨迹异常",
                summary=f"轨迹侧命中 {len(trip_hits)} 条可疑短停/折返记录。",
                category=ClueCategory.trip,
                risk_level=_to_risk_level(trip_lv),
                risk_score=round(trip_score, 2),
                rule_hits=["sensitive_short_return"],
                feature_snapshot={"suspicious_trip_count": len(trip_hits)},
                risk_prompts=_risk_prompts(trip_lv),
            )
        )

    collision_events = [
        ev
        for ev in (analytics.get("collision_result", {}).get("events") or [])
        if str(ev.get("person_id", "")) == person_id
        or str(ev.get("person_a", "")) == person_id
        or str(ev.get("person_b", "")) == person_id
    ]
    for ev in collision_events[:3]:
        if ev.get("type") == "rule_error":
            continue
        sc = float(ev.get("score") or risk_score)
        lv = classify_risk_level(sc)
        rid = str(ev.get("rule_id") or "multi_source")
        rows.append(
            Clue(
                case_id=case_id,
                person_id=person_id,
                title=f"多源碰撞：{rid}",
                summary=f"跨数据源规则命中，事件分 {sc:.1f}。",
                category=ClueCategory.other,
                risk_level=_to_risk_level(lv),
                risk_score=round(sc, 2),
                rule_hits=[rid],
                feature_snapshot=ev if isinstance(ev, dict) else {},
                risk_prompts=_risk_prompts(lv),
            )
        )

    if not rows:
        rows.append(
            Clue(
                case_id=case_id,
                person_id=person_id,
                title="综合风险评估",
                summary="已完成多源数据评估，当前未命中显著异常规则。",
                category=ClueCategory.other,
                risk_level=_to_risk_level(risk_level),
                risk_score=round(risk_score, 2),
                rule_hits=["risk_profile"],
                feature_snapshot={"profile": profile},
                risk_prompts=_risk_prompts(risk_level),
            )
        )
    return rows


def _advisory_lock(db: Session, *parts: object) -> None:
    key_raw = "|".join(str(p) for p in parts).encode("utf-8")
    lock_key = int.from_bytes(hashlib.sha256(key_raw).digest()[:8], "big", signed=True)
    db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": lock_key})


def _ensure_real_clues_if_empty(
    db: Session,
    minio: Minio,
    *,
    case_id: int,
    person_id: str,
) -> list:
    pid = (person_id or "").strip()
    if not pid:
        return []
    _advisory_lock(db, "clues_case", case_id)
    _advisory_lock(db, "clues_person", case_id, pid)
    rows = clue_repo.list_by_case_and_person(db, case_id=case_id, person_id=pid)
    if rows:
        return rows
    case_row = case_repo.get_by_id(db, case_id)
    if case_row is None:
        return []
    analytics = case_intel_service.run_case_analytics(
        db,
        minio,
        tenant_user_id=int(case_row.user_id),
        case_id=case_id,
    )
    real_rows = _build_real_clues_for_person(
        case_id=case_id,
        person_id=pid,
        analytics=analytics,
    )
    existing_titles = {
        r.title for r in clue_repo.list_by_case_and_person(db, case_id=case_id, person_id=pid)
    }
    to_insert = [r for r in real_rows if r.title not in existing_titles]
    clue_repo.bulk_add(db, to_insert)
    db.flush()
    return clue_repo.list_by_case_and_person(db, case_id=case_id, person_id=pid)


def ensure_case_clues(db: Session, minio: Minio, *, case_id: int, user: User) -> list:
    case_row = _ensure_case_owned(db, user, case_id)
    _advisory_lock(db, "clues_case", case_id)
    analytics = case_intel_service.run_case_analytics(
        db,
        minio,
        tenant_user_id=int(case_row.user_id),
        case_id=case_id,
    )
    persons = sorted(set(analytics.get("persons") or []))
    existing = clue_repo.list_by_case(db, case_id=case_id)
    existing_persons = {str(r.person_id) for r in existing}
    if existing and existing_persons.issuperset(persons):
        return existing
    to_add: list[Clue] = []
    for pid in persons:
        if pid in existing_persons:
            continue
        to_add.extend(
            _build_real_clues_for_person(
                case_id=case_id,
                person_id=pid,
                analytics=analytics,
            )
        )
    if to_add:
        clue_repo.bulk_add(db, to_add)
        db.flush()
    return clue_repo.list_by_case(db, case_id=case_id)


def list_clues_for_person(
    db: Session,
    neo4j: Driver,
    minio: Minio,
    *,
    user: User,
    case_id: int,
    person_id: str,
) -> list[dict]:
    case_row = _ensure_case_owned(db, user, case_id)
    tid = int(case_row.user_id)
    pid = (person_id or "").strip()
    edges = case_graph_service.load_case_transfer_edges(
        db, minio, tenant_user_id=tid, case_id=case_id
    )
    in_case = pid in case_graph_service.node_set_from_edges(edges)
    if not in_case and not graph_service.person_name_exists(neo4j, name=pid, tenant_id=tid):
        raise AppError(
            "人物不在图谱中或 person_id 与本案表格构图 / Neo4j 不一致",
            code=40401,
            status_code=404,
        )

    rows = _ensure_real_clues_if_empty(
        db,
        minio,
        case_id=case_id,
        person_id=pid,
    )

    return [
        {
            "id": r.id,
            "title": r.title,
            "risk_level": r.risk_level.value if hasattr(r.risk_level, "value") else str(r.risk_level),
            "risk_score": float(r.risk_score),
        }
        for r in rows
    ]


def get_clue_detail(
    db: Session,
    *,
    user: User,
    clue_id: int,
) -> dict:
    row = clue_repo.get_by_id(db, clue_id)
    if row is None:
        raise AppError("线索不存在", code=45001, status_code=404)
    _ensure_case_owned(db, user, row.case_id)

    def _cat(v) -> str:
        return v.value if hasattr(v, "value") else str(v)

    return {
        "id": row.id,
        "case_id": row.case_id,
        "person_id": row.person_id,
        "title": row.title,
        "summary": row.summary,
        "category": _cat(row.category),
        "risk_level": _cat(row.risk_level),
        "risk_score": float(row.risk_score),
        "rule_hits": row.rule_hits if isinstance(row.rule_hits, list) else [],
        "feature_snapshot": row.feature_snapshot if isinstance(row.feature_snapshot, dict) else {},
        "risk_prompts": row.risk_prompts if isinstance(row.risk_prompts, list) else [],
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
    }
