"""
型定義モジュール.

フロントエンドの frontend/src/types.ts と整合する dataclass を定義する。
API レスポンスでは dataclasses.asdict() で辞書に変換して使用する。
"""

from __future__ import annotations

import dataclasses
import datetime
import re
import zoneinfo

# 日本標準時 (JST) タイムゾーン
JST = zoneinfo.ZoneInfo("Asia/Tokyo")


def calculate_earthquake_time_range(
    detected_at_str: str,
    before_seconds: int = 30,
    after_seconds: int = 240,
) -> tuple[datetime.datetime, datetime.datetime]:
    """
    地震発生時刻から前後の時間範囲を計算する.

    Args:
        detected_at_str: 地震発生時刻（ISO 8601 形式、タイムゾーン情報付き）
        before_seconds: 地震発生前の許容秒数（デフォルト: 30）
        after_seconds: 地震発生後の許容秒数（デフォルト: 240 = 4分）

    Returns:
        (開始時刻, 終了時刻) のタプル

    """
    detected_at = datetime.datetime.fromisoformat(detected_at_str)
    return (
        detected_at - datetime.timedelta(seconds=before_seconds),
        detected_at + datetime.timedelta(seconds=after_seconds),
    )


@dataclasses.dataclass
class ParsedFilename:
    """
    スクリーンショットファイル名のパース結果.

    ファイル名フォーマット: PREFIX-YYYY-MM-DD-HHMMSS.png
    タイムスタンプは UTC として解釈される。
    """

    filename: str
    prefix: str
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int
    timestamp: str  # ISO 8601 形式 (UTC)


def parse_filename(filename: str) -> ParsedFilename | None:
    """
    スクリーンショットのファイル名からタイムスタンプ情報を抽出する.

    ファイル名のタイムスタンプは UTC として解釈される。

    Args:
        filename: スクリーンショットのファイル名（例: SHAKE-2025-08-12-104039.png）

    Returns:
        ParsedFilename または None（パース失敗時）

    """
    pattern = r"^(.+?)-(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})(\d{2})\.png$"
    match = re.match(pattern, filename)

    if not match:
        return None

    prefix, year, month, day, hour, minute, second = match.groups()

    # ファイル名のタイムスタンプは UTC
    timestamp_utc = datetime.datetime(
        int(year), int(month), int(day), int(hour), int(minute), int(second), tzinfo=datetime.UTC
    )

    return ParsedFilename(
        filename=filename,
        prefix=prefix,
        year=int(year),
        month=int(month),
        day=int(day),
        hour=int(hour),
        minute=int(minute),
        second=int(second),
        timestamp=timestamp_utc.isoformat(),
    )


@dataclasses.dataclass
class EarthquakeData:
    """
    地震データ.

    気象庁 API から取得した地震情報を表す。
    detected_at は JST (+09:00) で保存される。
    """

    id: int
    event_id: str
    detected_at: str  # ISO 8601 形式 (JST)
    latitude: float
    longitude: float
    magnitude: float
    depth: int
    epicenter_name: str
    max_intensity: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclasses.dataclass
class ScreenshotMetadata:
    """
    スクリーンショットのメタデータ.

    PNG ファイルから抽出した STA/LTA 値と、関連する地震情報を含む。
    """

    filename: str
    filepath: str
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int
    timestamp: str  # ISO 8601 形式 (UTC)
    sta: float | None = None
    lta: float | None = None
    sta_lta_ratio: float | None = None
    max_count: float | None = None
    metadata: str | None = None
    earthquake: dict | None = None  # EarthquakeData を辞書形式で保持


@dataclasses.dataclass
class DateInfo:
    """日付情報."""

    year: int
    month: int
    day: int


@dataclasses.dataclass
class SignalStatistics:
    """
    信号値の統計情報.

    スクリーンショットの max_count（最大振幅）に関する統計を表す。
    """

    total: int
    absolute_total: int = 0
    with_signal: int = 0
    min_signal: float | None = None
    max_signal: float | None = None
    avg_signal: float | None = None
    earthquake_count: int = 0


@dataclasses.dataclass
class ScreenshotRow:
    """
    SQLite から取得したスクリーンショット行データ.

    データベースの行から ScreenshotMetadata へ変換する際の中間表現。
    """

    filename: str
    filepath: str
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int
    timestamp: str
    sta_value: float | None
    lta_value: float | None
    sta_lta_ratio: float | None
    max_count: float | None
    metadata_raw: str | None
    earthquake_event_id: str | None = None


def _earthquake_to_dict(earthquake: EarthquakeData | dict | None) -> dict | None:
    """EarthquakeData または辞書を辞書に変換する."""
    if earthquake is None:
        return None
    if isinstance(earthquake, EarthquakeData):
        return dataclasses.asdict(earthquake)
    return earthquake


def row_to_screenshot_dict(row: tuple, earthquake: EarthquakeData | dict | None = None) -> dict:
    """
    SQLite の行データをスクリーンショット辞書に変換する.

    Args:
        row: SQLite から取得した行タプル（14要素または15要素）
        earthquake: 関連する地震情報（EarthquakeData または辞書、オプション）

    Returns:
        スクリーンショット情報の辞書

    """
    result: dict = {
        "filename": row[0],
        "filepath": row[1],
        "year": row[2],
        "month": row[3],
        "day": row[4],
        "hour": row[5],
        "minute": row[6],
        "second": row[7],
        "timestamp": row[8],
        "sta": row[9],
        "lta": row[10],
        "sta_lta_ratio": row[11],
        "max_count": row[12],
        "metadata": row[13],
    }
    eq_dict = _earthquake_to_dict(earthquake)
    if eq_dict is not None:
        result["earthquake"] = eq_dict
    return result


def screenshot_dict_to_response(
    screenshot: dict,
    earthquake: EarthquakeData | dict | None = None,
) -> dict:
    """
    スクリーンショット辞書を API レスポンス形式に変換する.

    Args:
        screenshot: スクリーンショット情報の辞書
        earthquake: 関連する地震情報（EarthquakeData または辞書、オプション）

    Returns:
        API レスポンス形式の辞書（prefix フィールド付き）

    """
    result: dict = {
        "filename": screenshot["filename"],
        "prefix": screenshot["filename"].split("-")[0],
        "year": screenshot["year"],
        "month": screenshot["month"],
        "day": screenshot["day"],
        "hour": screenshot["hour"],
        "minute": screenshot["minute"],
        "second": screenshot["second"],
        "timestamp": screenshot["timestamp"],
        "sta": screenshot.get("sta"),
        "lta": screenshot.get("lta"),
        "sta_lta_ratio": screenshot.get("sta_lta_ratio"),
        "max_count": screenshot.get("max_count"),
        "metadata": screenshot.get("metadata"),
    }
    # earthquake の処理
    if "earthquake" in screenshot and screenshot["earthquake"] is not None:
        result["earthquake"] = screenshot["earthquake"]
    else:
        eq_dict = _earthquake_to_dict(earthquake)
        if eq_dict is not None:
            result["earthquake"] = eq_dict
    return result
