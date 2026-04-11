"""
异步分析任务：mock / basic / iforest / graph。
可重试、全链路日志、失败不吞异常。
"""

from __future__ import annotations

import json
import logging
import random
from typing import Any

import numpy as np
import pandas as pd
from neo4j import GraphDatabase
from sklearn.ensemble import IsolationForest

from backend.core.config import get_settings
from backend.infra.redis_client import ttl_jittered
from backend.schema.analyze import AnalyzeGraphData, AnalyzeGraphUserItem, AnalyzeIforestData
from backend.service import data_pipeline_service
from backend.tasks.celery_app import celery_app
from backend.tasks import runtime
from backend.tasks.task_base import QuotaTrackedTask
from backend.utils.analyze_utils import analyze_cache_key, analyze_risk_level

logger = logging.getLogger("tasks.analyze_data")


def _attach_summary(payload: dict, summary_score: float) -> dict:
    s = round(float(summary_score), 1)
    disp: float | int = int(s) if float(s).is_integer() else s
    return {**payload, "score": disp, "level": analyze_risk_level(float(summary_score))}


def _run_graph_analysis(df: pd.DataFrame, user_id: int) -> dict[str, Any]:
    settings = get_settings()
    driver = GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )
    try:
        degrees: dict[str, int] = {}
        cypher_deg = (
            "MATCH (a:User {tenant_id: $tenant_id})-[:TRANSFER]->() "
            "RETURN a.name AS name, count(*) AS degree"
        )
        with driver.session() as session:
            for rec in session.run(cypher_deg, tenant_id=user_id):
                degrees[str(rec["name"])] = int(rec["degree"])

        colmap = {str(c).strip().lower(): c for c in df.columns}
        if "name" not in colmap or "amount" not in colmap:
            raise ValueError("csv requires name and amount columns")
        name_col, amt_col = colmap["name"], colmap["amount"]
        sub = df[[name_col, amt_col]].copy()
        sub[amt_col] = pd.to_numeric(sub[amt_col], errors="coerce").fillna(0.0)
        amounts: dict[str, float] = {}
        for k, v in sub.groupby(name_col, dropna=True)[amt_col].sum().items():
            if pd.isna(k):
                continue
            amounts[str(k)] = float(v)

        all_names = sorted(set(degrees.keys()) | set(amounts.keys()))
        max_deg = max(degrees.values(), default=0) or 1
        max_amt = max(amounts.values(), default=0.0) or 1.0
        users: list[AnalyzeGraphUserItem] = []
        for name in all_names:
            d = degrees.get(name, 0)
            a = amounts.get(name, 0.0)
            risk = min(100.0, (d / max_deg) * 50.0 + (a / max_amt) * 50.0)
            users.append(AnalyzeGraphUserItem(name=name, risk=int(round(risk))))
        summary = float(max((u.risk for u in users), default=0))
        data = AnalyzeGraphData(
            users=users,
            score=summary,
            level=analyze_risk_level(summary),
        )
        return {"code": 0, "kind": "graph", "user_id": user_id, "data": data.model_dump(mode="json")}
    finally:
        driver.close()


@celery_app.task(
    bind=True,
    base=QuotaTrackedTask,
    name="tasks.analyze_data_task",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 5, "countdown": 10},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def analyze_data_task(self, kind: str, filename: str, user_id: int) -> dict[str, Any]:
    logger.info(
        "analyze_data_task start kind=%s filename=%s user_id=%s retry=%s",
        kind,
        filename,
        user_id,
        getattr(self.request, "retries", 0),
    )
    try:
        if kind == "mock":
            score = float(random.randint(0, 100))
            return {
                "code": 0,
                "kind": "mock",
                "data": {"score": score, "level": analyze_risk_level(score)},
            }

        if not runtime.file_belongs_to_user(filename, user_id):
            return {"code": 1, "msg": "file not found", "data": None}

        rds = runtime.redis_client()
        mio = runtime.minio_client()
        db = runtime.open_session()
        try:
            if kind == "basic":
                cache_key = analyze_cache_key("basic", user_id, filename)
                cached = rds.get(cache_key)
                if cached is not None:
                    return json.loads(cached)

                summary = data_pipeline_service.run_standard_pipeline(
                    db, mio, filename=filename, user_id=user_id
                )
                feats = summary.get("features") or {}
                nums = [v for v in feats.values() if isinstance(v, (int, float)) and not isinstance(v, bool)]
                score = float(np.mean(nums)) if nums else 0.0
                if np.isnan(score):
                    score = 0.0
                raw = round(float(score), 1)
                body: dict[str, Any] = {
                    "code": 0,
                    "msg": "success",
                    "data": _attach_summary({"pipeline": summary}, float(raw)),
                }
                safe = json.loads(json.dumps(body, default=str))
                rds.setex(cache_key, ttl_jittered(300, 100), json.dumps(safe, ensure_ascii=False))
                return safe

            if kind == "iforest":
                cache_key = analyze_cache_key("iforest", user_id, filename)
                cached = rds.get(cache_key)
                if cached is not None:
                    return json.loads(cached)

                df_clean, pipeline_summary = data_pipeline_service.run_pipeline_dataframe(
                    db, mio, filename=filename, user_id=user_id
                )
                num_df = df_clean.select_dtypes(include=[np.integer, np.floating])
                x = num_df.dropna()
                total = int(len(x))
                if total == 0:
                    data = AnalyzeIforestData(total=0, anomaly=0, score=0.0, level="low")
                    out: dict[str, Any] = {
                        "code": 0,
                        "kind": "iforest",
                        "data": data.model_dump(mode="json"),
                        "pipeline": pipeline_summary,
                    }
                    safe = json.loads(json.dumps(out, default=str))
                    rds.setex(cache_key, ttl_jittered(300, 100), json.dumps(safe, ensure_ascii=False))
                    return safe
                clf = IsolationForest()
                pred = clf.fit_predict(x.to_numpy())
                anomaly = int((pred == -1).sum())
                summary_score = 100.0 * anomaly / total
                data = AnalyzeIforestData(
                    total=total,
                    anomaly=anomaly,
                    score=summary_score,
                    level=analyze_risk_level(summary_score),
                )
                out = {
                    "code": 0,
                    "kind": "iforest",
                    "data": data.model_dump(mode="json"),
                    "pipeline": pipeline_summary,
                }
                safe = json.loads(json.dumps(out, default=str))
                rds.setex(cache_key, ttl_jittered(300, 100), json.dumps(safe, ensure_ascii=False))
                return safe

            if kind == "graph":
                df_clean, _ = data_pipeline_service.run_pipeline_dataframe(
                    db, mio, filename=filename, user_id=user_id
                )
                return _run_graph_analysis(df_clean, user_id)

            return {"code": 1, "msg": f"unknown kind: {kind}", "data": None}
        finally:
            db.close()
    except Exception:
        logger.exception(
            "analyze_data_task FAILED kind=%s filename=%s user_id=%s retries=%s",
            kind,
            filename,
            user_id,
            getattr(self.request, "retries", 0),
        )
        if getattr(self.request, "retries", 0) >= int(getattr(self, "max_retries", 5) or 5):
            logger.error("analyze_data_task retries exhausted, propagating failure")
        raise
