# ruff: noqa: S101
"""
ScreenshotManager のユニットテスト.

スクリーンショットファイル管理とメタデータキャッシュ機能をテストします。
"""

import sqlite3
import zoneinfo
from datetime import UTC, datetime

from rsudp.screenshot_manager import ScreenshotManager

JST = zoneinfo.ZoneInfo("Asia/Tokyo")


class TestScreenshotManagerInit:
    """ScreenshotManager 初期化のテスト."""

    def test_init_creates_cache_database(self, screenshot_config):
        """キャッシュデータベースが作成されることを確認."""
        manager = ScreenshotManager(screenshot_config)

        assert manager.cache_path.exists()

    def test_init_creates_tables(self, screenshot_config):
        """screenshot_metadata テーブルが作成されることを確認."""
        manager = ScreenshotManager(screenshot_config)

        with sqlite3.connect(manager.cache_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='screenshot_metadata'"
            )
            result = cursor.fetchone()

        assert result is not None
        assert result[0] == "screenshot_metadata"


class TestParseFilename:
    """ファイル名解析のテスト."""

    def test_parse_valid_filename(self, screenshot_config):
        """有効なファイル名が正しくパースされることを確認."""
        manager = ScreenshotManager(screenshot_config)

        result = manager._parse_filename("SHAKE-2025-12-12-190542.png")

        assert result is not None
        assert result["prefix"] == "SHAKE"
        assert result["year"] == 2025
        assert result["month"] == 12
        assert result["day"] == 12
        assert result["hour"] == 19
        assert result["minute"] == 5
        assert result["second"] == 42
        assert "+00:00" in result["timestamp"]  # UTC

    def test_parse_alert_filename(self, screenshot_config):
        """ALERT プレフィックスのファイル名が正しくパースされることを確認."""
        manager = ScreenshotManager(screenshot_config)

        result = manager._parse_filename("ALERT-2025-08-14-091523.png")

        assert result is not None
        assert result["prefix"] == "ALERT"
        assert result["year"] == 2025
        assert result["month"] == 8
        assert result["day"] == 14

    def test_parse_invalid_filename_returns_none(self, screenshot_config):
        """無効なファイル名で None が返されることを確認."""
        manager = ScreenshotManager(screenshot_config)

        assert manager._parse_filename("invalid.png") is None
        assert manager._parse_filename("no-date.png") is None
        assert manager._parse_filename("SHAKE-2025-12-12.png") is None


class TestTimestampUTC:
    """タイムスタンプの UTC 処理テスト."""

    def test_filename_timestamp_is_utc(self, screenshot_config):
        """ファイル名から抽出されたタイムスタンプが UTC であることを確認."""
        manager = ScreenshotManager(screenshot_config)

        result = manager._parse_filename("SHAKE-2025-12-12-190542.png")

        assert result is not None

        # ISO フォーマットで UTC (+00:00) であることを確認
        assert result["timestamp"] == "2025-12-12T19:05:42+00:00"

        # datetime に変換して UTC であることを確認
        ts = datetime.fromisoformat(result["timestamp"])
        assert ts.tzinfo == UTC


class TestGetEarthquakeForScreenshot:
    """スクリーンショットに対応する地震検索のテスト."""

    def test_find_earthquake_for_screenshot(self, screenshot_config, sample_earthquake_jst):
        """スクリーンショットに対応する地震を検索できることを確認."""
        from rsudp.quake.database import QuakeDatabase

        # 地震データベースを作成（screenshot_config の quake パスを使用）
        quake_db_path = screenshot_config.data.quake
        quake_db = QuakeDatabase(screenshot_config)
        quake_db.insert_earthquake(**sample_earthquake_jst)

        manager = ScreenshotManager(screenshot_config)

        # 地震と同じ瞬間の UTC タイムスタンプ
        # 地震: 2025-12-13 04:05:00 JST = 2025-12-12 19:05:00 UTC
        screenshot_ts = "2025-12-12T19:05:00+00:00"

        result = manager.get_earthquake_for_screenshot(screenshot_ts, quake_db_path)

        assert result is not None
        assert result["event_id"] == "test-quake-001"

    def test_no_false_match_same_numbers_different_tz(self, screenshot_config):
        """同じ数字でもタイムゾーンが異なれば誤マッチしないことを確認."""
        from rsudp.quake.database import QuakeDatabase

        quake_db_path = screenshot_config.data.quake
        quake_db = QuakeDatabase(screenshot_config)

        # 地震: 2025-12-12 19:05:00 JST（ファイル名と同じ数字だが異なるタイムゾーン）
        jst_earthquake = {
            "event_id": "test-quake-002",
            "detected_at": datetime(2025, 12, 12, 19, 5, 0, tzinfo=JST),
            "latitude": 35.6,
            "longitude": 139.7,
            "magnitude": 4.5,
            "depth": 50,
            "epicenter_name": "茨城県南部",
            "max_intensity": "4",
        }
        quake_db.insert_earthquake(**jst_earthquake)

        manager = ScreenshotManager(screenshot_config)

        # スクリーンショット: 2025-12-12 19:05:00 UTC
        # 地震: 2025-12-12 19:05:00 JST（= 2025-12-12 10:05:00 UTC）
        # 差分: 9 時間
        screenshot_ts = "2025-12-12T19:05:00+00:00"

        result = manager.get_earthquake_for_screenshot(screenshot_ts, quake_db_path)

        # 9 時間離れているのでマッチしてはいけない
        assert result is None


class TestGetScreenshotsWithEarthquakeFilter:
    """地震フィルタ付きスクリーンショット取得のテスト."""

    def test_filter_matches_correct_earthquake(self, screenshot_config, sample_earthquake_jst):
        """地震フィルタが正しいタイムゾーンでマッチすることを確認."""
        from rsudp.quake.database import QuakeDatabase

        # 地震データベースを作成（screenshot_config の quake パスを使用）
        quake_db_path = screenshot_config.data.quake
        quake_db = QuakeDatabase(screenshot_config)
        quake_db.insert_earthquake(**sample_earthquake_jst)

        manager = ScreenshotManager(screenshot_config)

        # キャッシュにスクリーンショットを直接追加
        with sqlite3.connect(manager.cache_path) as conn:
            conn.execute(
                """
                INSERT INTO screenshot_metadata
                (filename, filepath, year, month, day, hour, minute, second,
                 timestamp, sta_value, lta_value, sta_lta_ratio, max_count,
                 created_at, file_size, metadata_raw)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    "SHAKE-2025-12-12-190500.png",
                    "2025/12/12/SHAKE-2025-12-12-190500.png",
                    2025,
                    12,
                    12,
                    19,
                    5,
                    0,
                    "2025-12-12T19:05:00+00:00",
                    100.0,
                    50.0,
                    2.0,
                    1000.0,
                    1234567890.0,
                    12345,
                    None,
                ),
            )

        result = manager.get_screenshots_with_earthquake_filter(quake_db_path=quake_db_path)

        assert len(result) == 1
        assert result[0]["earthquake"]["event_id"] == "test-quake-001"

    def test_filter_no_false_match(self, screenshot_config):
        """地震フィルタが誤マッチしないことを確認."""
        from rsudp.quake.database import QuakeDatabase

        quake_db_path = screenshot_config.data.quake
        quake_db = QuakeDatabase(screenshot_config)

        # 地震: 2025-12-12 19:05:00 JST
        jst_earthquake = {
            "event_id": "test-quake-004",
            "detected_at": datetime(2025, 12, 12, 19, 5, 0, tzinfo=JST),
            "latitude": 35.6,
            "longitude": 139.7,
            "magnitude": 4.5,
            "depth": 50,
            "epicenter_name": "茨城県南部",
            "max_intensity": "4",
        }
        quake_db.insert_earthquake(**jst_earthquake)

        manager = ScreenshotManager(screenshot_config)

        # スクリーンショット: 2025-12-12 19:05:00 UTC（地震と 9 時間離れている）
        with sqlite3.connect(manager.cache_path) as conn:
            conn.execute(
                """
                INSERT INTO screenshot_metadata
                (filename, filepath, year, month, day, hour, minute, second,
                 timestamp, sta_value, lta_value, sta_lta_ratio, max_count,
                 created_at, file_size, metadata_raw)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    "SHAKE-2025-12-12-190500.png",
                    "2025/12/12/SHAKE-2025-12-12-190500.png",
                    2025,
                    12,
                    12,
                    19,
                    5,
                    0,
                    "2025-12-12T19:05:00+00:00",
                    100.0,
                    50.0,
                    2.0,
                    1000.0,
                    1234567890.0,
                    12345,
                    None,
                ),
            )

        result = manager.get_screenshots_with_earthquake_filter(quake_db_path=quake_db_path)

        # 9 時間離れているのでマッチしてはいけない
        assert len(result) == 0


class TestGetSignalStatistics:
    """統計情報取得のテスト."""

    def test_get_signal_statistics_empty(self, screenshot_config):
        """データがない場合の統計情報を確認."""
        manager = ScreenshotManager(screenshot_config)

        result = manager.get_signal_statistics()

        assert result["total"] == 0

    def test_get_signal_statistics_with_data(self, screenshot_config):
        """データがある場合の統計情報を確認."""
        manager = ScreenshotManager(screenshot_config)

        # キャッシュにデータを追加
        with sqlite3.connect(manager.cache_path) as conn:
            conn.execute(
                """
                INSERT INTO screenshot_metadata
                (filename, filepath, year, month, day, hour, minute, second,
                 timestamp, sta_value, lta_value, sta_lta_ratio, max_count,
                 created_at, file_size, metadata_raw)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    "SHAKE-2025-12-12-190500.png",
                    "2025/12/12/SHAKE-2025-12-12-190500.png",
                    2025,
                    12,
                    12,
                    19,
                    5,
                    0,
                    "2025-12-12T19:05:00+00:00",
                    100.0,
                    50.0,
                    2.0,
                    1000.0,
                    1234567890.0,
                    12345,
                    None,
                ),
            )

        result = manager.get_signal_statistics()

        assert result["total"] == 1
