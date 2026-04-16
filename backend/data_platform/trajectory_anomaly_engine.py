"""
出行轨迹异常分析：敏感区域短停折返、时空伴随（BallTree / Haversine）。

输入 DataFrame 建议列：
- person_id: 人员标识
- timestamp: 定位时间（datetime 或可解析）
- lat, lng: WGS84 纬度、经度（度）

敏感区域：由 sensitive_points 传入 [(lat, lng), ...]，以各点为中心 500m 为「进入区域」。

输出：
{
  "suspicious_trips": [ ... ],
  "co_occurrence": [ ... ],
}
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

REQUIRED_COLS = frozenset({"person_id", "timestamp", "lat", "lng"})

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(
    lat1: np.ndarray | float,
    lon1: np.ndarray | float,
    lat2: np.ndarray | float,
    lon2: np.ndarray | float,
) -> np.ndarray | float:
    """两点间大圆距离（米）。支持标量或广播数组。"""
    rlat1 = np.radians(np.asarray(lat1, dtype=float))
    rlon1 = np.radians(np.asarray(lon1, dtype=float))
    rlat2 = np.radians(np.asarray(lat2, dtype=float))
    rlon2 = np.radians(np.asarray(lon2, dtype=float))
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = np.sin(dlat / 2.0) ** 2 + np.cos(rlat1) * np.cos(rlat2) * np.sin(dlon / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_M * np.arcsin(np.minimum(1.0, np.sqrt(a)))


def _parse_ts(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", format="mixed")


def detect_sensitive_short_return(
    df: pd.DataFrame,
    sensitive_points: list[tuple[float, float]],
    *,
    radius_m: float = 500.0,
    max_stay: timedelta = timedelta(minutes=5),
) -> list[dict[str, Any]]:
    """
    敏感区域折返：进入敏感圆（半径 radius_m）→ 停留时长 < max_stay → 离开圆（距离 > radius_m）。

    「返回」理解为离开敏感区域（回到圆外），即短停后驶离。
    """
    if (
        df.empty
        or not REQUIRED_COLS.issubset(df.columns)
        or not sensitive_points
    ):
        return []

    out: list[dict[str, Any]] = []
    max_stay_sec = max_stay.total_seconds()

    for person, g in df.groupby("person_id", sort=False):
        g = g.sort_values("timestamp").reset_index(drop=True)
        tcol = _parse_ts(g["timestamp"])
        lat = g["lat"].astype(float).values
        lon = g["lng"].astype(float).values
        times = tcol.values

        for sp_idx, (slat, slng) in enumerate(sensitive_points):
            # 状态机：圆外 -> 圆内 -> 圆外
            inside = False
            entry_i: int | None = None

            for i in range(len(g)):
                d = float(haversine_m(lat[i], lon[i], slat, slng))
                in_zone = d <= radius_m

                if not inside and in_zone:
                    inside = True
                    entry_i = i
                    continue

                if inside and not in_zone:
                    # 离开敏感区
                    assert entry_i is not None
                    t0 = pd.Timestamp(times[entry_i])
                    t1 = pd.Timestamp(times[i])
                    stay_sec = (t1 - t0).total_seconds()
                    if stay_sec < max_stay_sec and stay_sec >= 0:
                        out.append(
                            {
                                "type": "sensitive_short_return",
                                "person_id": str(person),
                                "sensitive_point_index": sp_idx,
                                "sensitive_lat": float(slat),
                                "sensitive_lng": float(slng),
                                "enter_time": t0.isoformat(),
                                "exit_time": t1.isoformat(),
                                "stay_seconds": round(stay_sec, 3),
                                "radius_m": radius_m,
                                "max_stay_seconds": max_stay_sec,
                            }
                        )
                    inside = False
                    entry_i = None

            # 轨迹结束仍在区内：不视为完整「折返」，不输出

    return out


def detect_spatiotemporal_cooccurrence(
    df: pd.DataFrame,
    *,
    radius_m: float = 500.0,
    max_time_delta: timedelta = timedelta(minutes=30),
) -> list[dict[str, Any]]:
    """
    时空伴随：不同人员两点之间 |Δt| ≤ max_time_delta 且球面距离 ≤ radius_m。

    使用 sklearn BallTree（metric=haversine）做空间半径查询，再按时间窗过滤。
    """
    if df.empty or not REQUIRED_COLS.issubset(df.columns):
        return []

    work = df.copy()
    work["_ts"] = _parse_ts(work["timestamp"])
    work = work.dropna(subset=["_ts"])
    if work.empty:
        return []

    work = work.sort_values("_ts").reset_index(drop=True)
    n = len(work)
    lat = work["lat"].astype(float).values
    lon = work["lng"].astype(float).values
    persons = work["person_id"].astype(str).values
    times = work["_ts"].values

    # Haversine BallTree：输入为弧度 (lat, lon)
    coords_rad = np.radians(np.column_stack([lat, lon]))
    r_rad = radius_m / EARTH_RADIUS_M
    tree = BallTree(coords_rad, metric="haversine")

    max_sec = max_time_delta.total_seconds()

    seen: set[tuple[int, int]] = set()
    results: list[dict[str, Any]] = []

    for i in range(n):
        # 空间邻居（含自身）
        neigh = tree.query_radius(coords_rad[i : i + 1], r=r_rad, return_distance=False)[
            0
        ]
        for j in neigh:
            if j <= i:
                continue
            if persons[i] == persons[j]:
                continue
            dsec = abs(
                (pd.Timestamp(times[j]) - pd.Timestamp(times[i])).total_seconds()
            )
            if dsec > max_sec:
                continue
            key = (i, j)
            if key in seen:
                continue
            seen.add(key)
            dist = float(haversine_m(lat[i], lon[i], lat[j], lon[j]))
            if persons[i] <= persons[j]:
                pa, pb = persons[i], persons[j]
                ta, tb = times[i], times[j]
                laa, loa, lab, lob = lat[i], lon[i], lat[j], lon[j]
            else:
                pa, pb = persons[j], persons[i]
                ta, tb = times[j], times[i]
                laa, loa, lab, lob = lat[j], lon[j], lat[i], lon[i]
            results.append(
                {
                    "type": "spatiotemporal_cooccurrence",
                    "person_a": pa,
                    "person_b": pb,
                    "time_a": pd.Timestamp(ta).isoformat(),
                    "time_b": pd.Timestamp(tb).isoformat(),
                    "lat_a": float(laa),
                    "lng_a": float(loa),
                    "lat_b": float(lab),
                    "lng_b": float(lob),
                    "distance_m": round(dist, 2),
                    "time_delta_seconds": round(
                        abs(
                            (pd.Timestamp(tb) - pd.Timestamp(ta)).total_seconds()
                        ),
                        3,
                    ),
                    "radius_m": radius_m,
                    "max_time_delta_minutes": max_time_delta.total_seconds() / 60.0,
                }
            )

    return results


def analyze_trajectory(
    df: pd.DataFrame | None,
    sensitive_points: list[tuple[float, float]] | None = None,
    *,
    radius_m: float = 500.0,
    sensitive_max_stay: timedelta = timedelta(minutes=5),
    cooccur_max_time: timedelta = timedelta(minutes=30),
) -> dict[str, Any]:
    """
    汇总敏感区短停折返与时空伴随。

    sensitive_points 为空列表时仅做时空伴随。
    """
    if df is None:
        df = pd.DataFrame()
    df = df.copy()
    if not df.empty and "timestamp" in df.columns:
        df["timestamp"] = _parse_ts(df["timestamp"])

    if not df.empty and not REQUIRED_COLS.issubset(df.columns):
        missing = REQUIRED_COLS - set(df.columns)
        raise ValueError(f"缺少列: {missing}")

    sp = sensitive_points if sensitive_points is not None else []

    suspicious = detect_sensitive_short_return(
        df,
        sp,
        radius_m=radius_m,
        max_stay=sensitive_max_stay,
    )
    cooc = detect_spatiotemporal_cooccurrence(
        df,
        radius_m=radius_m,
        max_time_delta=cooccur_max_time,
    )

    return {
        "suspicious_trips": suspicious,
        "co_occurrence": cooc,
    }


# ---------------------------------------------------------------------------
# 示例
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    # 敏感点：某卡口附近
    sens = [(39.9042, 116.4074)]

    demo = pd.DataFrame(
        [
            # P1：接近敏感点 → 2 分钟内离开（折返/短停）
            ("P1", "2024-07-01 10:00:00", 39.9040, 116.4070),
            ("P1", "2024-07-01 10:01:30", 39.9042, 116.4074),
            # 离开敏感点 >500m（相对 39.9042,116.4074）
            ("P1", "2024-07-01 10:02:00", 39.9100, 116.4120),
            # P2：与 P1 近且时间差小 → 伴随
            ("P2", "2024-07-01 10:01:45", 39.9043, 116.4075),
            ("P2", "2024-07-01 12:00:00", 40.0, 117.0),
        ],
        columns=["person_id", "timestamp", "lat", "lng"],
    )

    r = analyze_trajectory(demo, sensitive_points=sens)
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
