from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.model.models import FieldMappingMemory

_RUNTIME_MAPPING_CACHE: dict[tuple[int, str], dict[str, str]] = {}


def list_by_user(db: Session, *, user_id: int) -> list[FieldMappingMemory]:
    q = select(FieldMappingMemory).where(FieldMappingMemory.user_id == user_id)
    return list(db.execute(q).scalars().all())


def find_best_mapping(
    db: Session,
    *,
    user_id: int,
    header_signature: str,
    min_similarity: float = 80.0,
    touch_usage: bool = True,
) -> tuple[dict[str, str], float]:
    cache_key = (int(user_id), str(header_signature))
    cached = _RUNTIME_MAPPING_CACHE.get(cache_key)
    if cached:
        return dict(cached), 100.0

    rows = list_by_user(db, user_id=user_id)
    if not rows:
        return {}, 0.0
    grouped: dict[str, list[FieldMappingMemory]] = defaultdict(list)
    for row in rows:
        grouped[str(row.header_signature)].append(row)
    best_sig = None
    best_score = 0.0
    for sig in grouped:
        sc = float(fuzz.WRatio(str(header_signature), str(sig)))
        if sc > best_score:
            best_score = sc
            best_sig = sig
    if not best_sig or best_score < float(min_similarity):
        return {}, best_score
    best_rows: dict[str, FieldMappingMemory] = {}
    for r in grouped[best_sig]:
        src = str(r.source_field)
        prev = best_rows.get(src)
        if prev is None:
            best_rows[src] = r
            continue
        prev_key = (float(prev.confidence or 0.0), int(prev.hit_count or 0), int(prev.id or 0))
        cur_key = (float(r.confidence or 0.0), int(r.hit_count or 0), int(r.id or 0))
        if cur_key > prev_key:
            best_rows[src] = r
    mapping = {str(src): str(r.target_field) for src, r in best_rows.items()}
    _RUNTIME_MAPPING_CACHE[cache_key] = dict(mapping)
    if touch_usage:
        now = datetime.now(timezone.utc)
        for row in best_rows.values():
            row.hit_count = int(row.hit_count or 0) + 1
            row.last_used_at = now
            db.add(row)
        db.flush()
    return mapping, best_score


def upsert_mapping(
    db: Session,
    *,
    user_id: int,
    header_signature: str,
    mapping: dict[str, str],
    confidence_by_source: dict[str, float] | None = None,
) -> None:
    if not mapping:
        return
    now = datetime.now(timezone.utc)
    existing = list_by_user(db, user_id=user_id)
    index = {(str(r.header_signature), str(r.source_field)): r for r in existing}
    for source, target in mapping.items():
        key = (str(header_signature), str(source))
        conf = float((confidence_by_source or {}).get(str(source), 0.0))
        row = index.get(key)
        if row is None:
            row = FieldMappingMemory(
                user_id=user_id,
                header_signature=str(header_signature),
                source_field=str(source),
                target_field=str(target),
                confidence=conf,
                hit_count=1,
                last_used_at=now,
            )
        else:
            row.target_field = str(target)
            row.confidence = conf if conf > 0 else row.confidence
            row.hit_count = int(row.hit_count or 0) + 1
            row.last_used_at = now
        db.add(row)
    _RUNTIME_MAPPING_CACHE[(int(user_id), str(header_signature))] = {
        str(k): str(v) for k, v in mapping.items()
    }
    db.flush()
