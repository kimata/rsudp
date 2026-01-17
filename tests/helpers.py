"""
テストヘルパー関数

テスト全体で使用する共通のヘルパー関数を定義します。
"""

import datetime
import sqlite3

import rsudp.quake.database
import rsudp.types


def insert_test_earthquake(
    quake_db: rsudp.quake.database.QuakeDatabase,
    *,
    event_id: str = "test-quake-001",
    detected_at: datetime.datetime | None = None,
    latitude: float = 35.6,
    longitude: float = 139.7,
    magnitude: float = 4.5,
    depth: int = 50,
    epicenter_name: str = "茨城県南部",
    max_intensity: str | None = "4",
) -> bool:
    """
    テスト用の地震データを挿入するヘルパー.

    テストコードでの辞書展開による型エラーを回避するための関数.
    """
    if detected_at is None:
        detected_at = datetime.datetime(2025, 12, 12, 19, 5, 0, tzinfo=rsudp.types.JST)

    return quake_db.insert_earthquake(
        event_id=event_id,
        detected_at=detected_at,
        latitude=latitude,
        longitude=longitude,
        magnitude=magnitude,
        depth=depth,
        epicenter_name=epicenter_name,
        max_intensity=max_intensity,
    )


def insert_screenshot_metadata(
    conn: sqlite3.Connection,
    filename: str = "SHAKE-2025-12-12-190500.png",
    *,
    filepath: str | None = None,
    year: int = 2025,
    month: int = 12,
    day: int = 12,
    hour: int = 19,
    minute: int = 5,
    second: int = 0,
    timestamp: str = "2025-12-12T19:05:00+00:00",
    sta_value: float = 100.0,
    lta_value: float = 50.0,
    sta_lta_ratio: float = 2.0,
    max_count: float = 1000.0,
    created_at: float = 1234567890.0,
    file_size: int = 12345,
    metadata_raw: str | None = None,
    earthquake_event_id: str | None = None,
):
    """
    スクリーンショットメタデータをキャッシュに挿入するヘルパー.

    テストコードでの SQL INSERT 文の重複を避けるための共通関数.
    earthquake_event_id が指定された場合はそのカラムも含めて挿入.
    """
    if filepath is None:
        filepath = f"{year}/{month:02d}/{day:02d}/{filename}"

    if earthquake_event_id is not None:
        conn.execute(
            """
            INSERT INTO screenshot_metadata
            (filename, filepath, year, month, day, hour, minute, second,
             timestamp, sta_value, lta_value, sta_lta_ratio, max_count,
             created_at, file_size, metadata_raw, earthquake_event_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                filename,
                filepath,
                year,
                month,
                day,
                hour,
                minute,
                second,
                timestamp,
                sta_value,
                lta_value,
                sta_lta_ratio,
                max_count,
                created_at,
                file_size,
                metadata_raw,
                earthquake_event_id,
            ),
        )
    else:
        conn.execute(
            """
            INSERT INTO screenshot_metadata
            (filename, filepath, year, month, day, hour, minute, second,
             timestamp, sta_value, lta_value, sta_lta_ratio, max_count,
             created_at, file_size, metadata_raw)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                filename,
                filepath,
                year,
                month,
                day,
                hour,
                minute,
                second,
                timestamp,
                sta_value,
                lta_value,
                sta_lta_ratio,
                max_count,
                created_at,
                file_size,
                metadata_raw,
            ),
        )
