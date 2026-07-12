"""
統計 API 用の集計ロジック.

cache.db（screenshot_metadata）と quake.db（earthquakes）を読み取り専用で
直接 SQL 参照して集計する。ScreenshotManager / QuakeDatabase の状態は変更しない。
存在しない DB / テーブルは空データとして扱い、例外を送出しない。
"""

import collections
import dataclasses
import datetime
import math
import sqlite3
from pathlib import Path

import rsudp.config
import rsudp.types

# max_count ヒストグラムのビン下限境界（対数寄り）。最後は開区間 (10000+)。
_DISTRIBUTION_BOUNDS: tuple[int, ...] = (0, 100, 200, 500, 1000, 2000, 5000, 10000)

# 地震窓のデフォルト（前後秒数）
_QUAKE_BEFORE_SECONDS = 30
_QUAKE_AFTER_SECONDS = 240


@dataclasses.dataclass
class DailyCount:
    """JST 日付ごとのスクリーンショット件数."""

    date: str
    count: int


@dataclasses.dataclass
class DistributionBin:
    """max_count ヒストグラムの 1 ビン."""

    label: str
    min: float
    max: float | None
    count: int


@dataclasses.dataclass
class AssociationCount:
    """JST 日付ごとの全件数と地震照合件数."""

    date: str
    total: int
    matched: int


@dataclasses.dataclass
class StationLocation:
    """観測局の位置."""

    latitude: float
    longitude: float


@dataclasses.dataclass
class SensitivityPoint:
    """検出感度分析の 1 点（1 地震に対応）."""

    event_id: str
    epicenter_name: str
    distance_km: float
    magnitude: float
    depth: int
    max_count: float
    detected_at: str


@dataclasses.dataclass
class SensitivityResult:
    """検出感度分析の結果."""

    station: StationLocation | None
    points: list[SensitivityPoint]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    2 地点間の大円距離（km）を haversine 公式で計算する.

    Args:
        lat1, lon1: 地点 1 の緯度・経度（度）
        lat2, lon2: 地点 2 の緯度・経度（度）

    Returns:
        距離（km）

    """
    earth_radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return 2 * earth_radius_km * math.asin(math.sqrt(a))


def _to_jst_date(timestamp_str: str) -> str:
    """UTC の ISO タイムスタンプ文字列を JST の日付文字列 (YYYY-MM-DD) に変換する."""
    ts = datetime.datetime.fromisoformat(timestamp_str)
    return ts.astimezone(rsudp.types.JST).date().isoformat()


def _utc_cutoff_iso(days: int) -> str:
    """
    現在時刻から days 日遡った UTC の ISO 文字列を返す（timestamp 列との比較用）.

    timestamp 列は秒精度（マイクロ秒なし）の固定フォーマットで格納されているため、
    文字列比較が正しく機能するよう cutoff も同じ秒精度に丸める。
    """
    cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=days)
    return cutoff.replace(microsecond=0).isoformat()


def get_daily_counts(cache_path: Path, days: int = 90) -> list[DailyCount]:
    """
    JST 日付ごとのスクリーンショット件数を集計する.

    Args:
        cache_path: cache.db のパス
        days: 遡る日数

    Returns:
        日付昇順の DailyCount のリスト

    """
    if not cache_path.exists():
        return []

    cutoff = _utc_cutoff_iso(days)
    counts: collections.Counter[str] = collections.Counter()
    try:
        with sqlite3.connect(cache_path) as conn:
            cursor = conn.execute(
                "SELECT timestamp FROM screenshot_metadata WHERE timestamp >= ?",
                (cutoff,),
            )
            for (timestamp_str,) in cursor:
                counts[_to_jst_date(timestamp_str)] += 1
    except sqlite3.Error:
        return []

    return [DailyCount(date=date, count=counts[date]) for date in sorted(counts)]


def _bin_index(value: float) -> int:
    """max_count 値が属するビンのインデックスを返す."""
    for i in range(len(_DISTRIBUTION_BOUNDS) - 1):
        if value < _DISTRIBUTION_BOUNDS[i + 1]:
            return i
    return len(_DISTRIBUTION_BOUNDS) - 1


def _make_distribution_bins() -> list[DistributionBin]:
    """境界定義から空の（count=0）ビン列を構築する."""
    bins: list[DistributionBin] = []
    for i, lower in enumerate(_DISTRIBUTION_BOUNDS):
        upper = _DISTRIBUTION_BOUNDS[i + 1] if i + 1 < len(_DISTRIBUTION_BOUNDS) else None
        label = f"{lower}–{int(upper)}" if upper is not None else f"{lower}+"
        max_value = float(upper) if upper is not None else None
        bins.append(DistributionBin(label=label, min=float(lower), max=max_value, count=0))
    return bins


def get_distribution(cache_path: Path) -> list[DistributionBin]:
    """
    max_count のヒストグラムを集計する（max_count が NULL の行は除外）.

    Args:
        cache_path: cache.db のパス

    Returns:
        DistributionBin のリスト

    """
    bins = _make_distribution_bins()
    if not cache_path.exists():
        return bins

    try:
        with sqlite3.connect(cache_path) as conn:
            cursor = conn.execute("SELECT max_count FROM screenshot_metadata WHERE max_count IS NOT NULL")
            for (max_count,) in cursor:
                bins[_bin_index(float(max_count))].count += 1
    except sqlite3.Error:
        return _make_distribution_bins()

    return bins


def get_association(cache_path: Path, days: int = 90) -> list[AssociationCount]:
    """
    JST 日付ごとの全件数と地震照合件数（earthquake_event_id 非 NULL）を集計する.

    Args:
        cache_path: cache.db のパス
        days: 遡る日数

    Returns:
        日付昇順の AssociationCount のリスト

    """
    if not cache_path.exists():
        return []

    cutoff = _utc_cutoff_iso(days)
    total: collections.Counter[str] = collections.Counter()
    matched: collections.Counter[str] = collections.Counter()
    try:
        with sqlite3.connect(cache_path) as conn:
            cursor = conn.execute(
                "SELECT timestamp, earthquake_event_id FROM screenshot_metadata WHERE timestamp >= ?",
                (cutoff,),
            )
            for timestamp_str, event_id in cursor:
                date = _to_jst_date(timestamp_str)
                total[date] += 1
                if event_id is not None:
                    matched[date] += 1
    except sqlite3.Error:
        return []

    return [AssociationCount(date=date, total=total[date], matched=matched[date]) for date in sorted(total)]


def _max_count_in_window(
    conn: sqlite3.Connection,
    start_utc_iso: str,
    end_utc_iso: str,
) -> float | None:
    """指定 UTC 時間窓内の max_count 最大値を返す（該当なしは None）."""
    cursor = conn.execute(
        """
        SELECT MAX(max_count) FROM screenshot_metadata
        WHERE max_count IS NOT NULL AND timestamp >= ? AND timestamp <= ?
        """,
        (start_utc_iso, end_utc_iso),
    )
    row = cursor.fetchone()
    if row is None or row[0] is None:
        return None
    return float(row[0])


def get_sensitivity(
    cache_path: Path,
    quake_path: Path,
    station: rsudp.config.StationConfig | None,
) -> SensitivityResult:
    """
    各地震の時間窓内スクリーンショットの max_count 最大値と震央距離から検出感度を集計する.

    Args:
        cache_path: cache.db のパス
        quake_path: quake.db のパス
        station: 観測局の位置（None なら空結果）

    Returns:
        SensitivityResult（station が None なら points は空）

    """
    if station is None:
        return SensitivityResult(station=None, points=[])

    station_location = StationLocation(latitude=station.latitude, longitude=station.longitude)

    if not cache_path.exists() or not quake_path.exists():
        return SensitivityResult(station=station_location, points=[])

    points: list[SensitivityPoint] = []
    try:
        with sqlite3.connect(quake_path) as quake_conn:
            quake_rows = quake_conn.execute(
                """
                SELECT event_id, detected_at, latitude, longitude, magnitude, depth, epicenter_name
                FROM earthquakes
                """
            ).fetchall()

        with sqlite3.connect(cache_path) as cache_conn:
            for event_id, detected_at, latitude, longitude, magnitude, depth, epicenter_name in quake_rows:
                start, end = rsudp.types.calculate_earthquake_time_range(
                    detected_at,
                    before_seconds=_QUAKE_BEFORE_SECONDS,
                    after_seconds=_QUAKE_AFTER_SECONDS,
                )
                start_utc = start.astimezone(datetime.UTC).isoformat()
                end_utc = end.astimezone(datetime.UTC).isoformat()
                max_count = _max_count_in_window(cache_conn, start_utc, end_utc)
                if max_count is None:
                    continue
                distance_km = haversine_km(
                    station.latitude, station.longitude, float(latitude), float(longitude)
                )
                points.append(
                    SensitivityPoint(
                        event_id=event_id,
                        epicenter_name=epicenter_name,
                        distance_km=round(distance_km, 1),
                        magnitude=float(magnitude),
                        depth=int(depth),
                        max_count=max_count,
                        detected_at=detected_at,
                    )
                )
    except sqlite3.Error:
        return SensitivityResult(station=station_location, points=[])

    return SensitivityResult(station=station_location, points=points)
