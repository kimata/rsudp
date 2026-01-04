# ruff: noqa: S101
"""
タイムゾーン処理のテスト.

このテストは、UTC（スクリーンショット）と JST（地震データ）の
タイムゾーン比較が正しく動作することを検証する.
"""

import sqlite3
import zoneinfo
from datetime import UTC, datetime

from rsudp.quake.database import QuakeDatabase
from rsudp.screenshot_manager import ScreenshotManager

JST = zoneinfo.ZoneInfo("Asia/Tokyo")


class TestTimezoneComparison:
    """タイムゾーン比較の基本テスト."""

    def test_same_instant_different_timezone(self):
        """同じ瞬間を指す異なるタイムゾーンの datetime が等しいことを確認."""
        # 2025-12-12 19:05:00 UTC = 2025-12-13 04:05:00 JST
        utc_time = datetime(2025, 12, 12, 19, 5, 0, tzinfo=UTC)
        jst_time = datetime(2025, 12, 13, 4, 5, 0, tzinfo=JST)

        assert utc_time == jst_time
        assert (utc_time - jst_time).total_seconds() == 0

    def test_nine_hour_difference(self):
        """JST は UTC より 9 時間進んでいることを確認."""
        utc_time = datetime(2025, 12, 12, 19, 5, 0, tzinfo=UTC)
        jst_same_numbers = datetime(2025, 12, 12, 19, 5, 0, tzinfo=JST)

        # 同じ数字でも JST は 9 時間前の瞬間を指す
        diff = (utc_time - jst_same_numbers).total_seconds()
        assert diff == 9 * 3600  # 9時間 = 32400秒


class TestQuakeDatabaseTimezone:
    """QuakeDatabase のタイムゾーン処理テスト."""

    def test_get_earthquake_for_utc_timestamp(self, quake_db_config, sample_earthquake_jst):
        """UTC タイムスタンプで JST 地震データを正しく検索できることを確認."""
        db = QuakeDatabase(quake_db_config)

        # JST で地震データを挿入
        db.insert_earthquake(**sample_earthquake_jst)

        # UTC タイムスタンプで検索（同じ瞬間を指す）
        # 地震発生: 2025-12-13 04:05:00 JST = 2025-12-12 19:05:00 UTC
        utc_timestamp = datetime(2025, 12, 12, 19, 5, 0, tzinfo=UTC)

        result = db.get_earthquake_for_timestamp(utc_timestamp)

        assert result is not None
        assert result["event_id"] == "test-quake-001"

    def test_get_earthquake_within_time_window(self, quake_db_config, sample_earthquake_jst):
        """時間窓内のタイムスタンプで地震を検索できることを確認."""
        db = QuakeDatabase(quake_db_config)
        db.insert_earthquake(**sample_earthquake_jst)

        # 地震の 2 分後（after_seconds=240 のデフォルト範囲内）
        search_time = datetime(2025, 12, 12, 19, 7, 0, tzinfo=UTC)

        result = db.get_earthquake_for_timestamp(search_time)

        assert result is not None
        assert result["event_id"] == "test-quake-001"

    def test_get_earthquake_outside_time_window(self, quake_db_config, sample_earthquake_jst):
        """時間窓外のタイムスタンプでは地震が見つからないことを確認."""
        db = QuakeDatabase(quake_db_config)
        db.insert_earthquake(**sample_earthquake_jst)

        # 地震の 10 分後（after_seconds=240 の範囲外）
        search_time = datetime(2025, 12, 12, 19, 15, 0, tzinfo=UTC)

        result = db.get_earthquake_for_timestamp(search_time)

        assert result is None

    def test_no_false_match_with_same_numbers(self, quake_db_config, sample_earthquake_jst):
        """
        同じ数字でもタイムゾーンが異なれば誤マッチしないことを確認.

        これは以前のバグの再発防止テスト。
        地震: 2025-12-13 04:05:00 JST
        検索: 2025-12-13 04:05:00 UTC（= 2025-12-13 13:05:00 JST、9時間後）
        """
        db = QuakeDatabase(quake_db_config)
        db.insert_earthquake(**sample_earthquake_jst)

        # 同じ数字だが UTC（実際は 9 時間後）
        wrong_match_time = datetime(2025, 12, 13, 4, 5, 0, tzinfo=UTC)

        result = db.get_earthquake_for_timestamp(wrong_match_time)

        # 9 時間離れているのでマッチしてはいけない
        assert result is None


class TestScreenshotManagerTimezone:
    """ScreenshotManager のタイムゾーン処理テスト."""

    def test_get_earthquake_for_screenshot_utc(self, screenshot_config, sample_earthquake_jst):
        """UTC スクリーンショットタイムスタンプで JST 地震データを検索できることを確認."""
        # 地震データベースを作成
        quake_db_path = screenshot_config.data.quake
        quake_db = QuakeDatabase(screenshot_config)
        quake_db.insert_earthquake(**sample_earthquake_jst)

        # ScreenshotManager を作成
        manager = ScreenshotManager(screenshot_config)

        # UTC タイムスタンプで検索
        # スクリーンショット: 2025-12-12 19:05:00 UTC
        # 地震: 2025-12-13 04:05:00 JST（同じ瞬間）
        screenshot_ts = "2025-12-12T19:05:00+00:00"

        result = manager.get_earthquake_for_screenshot(screenshot_ts, quake_db_path)

        assert result is not None
        assert result["event_id"] == "test-quake-001"

    def test_no_false_match_for_screenshot(self, screenshot_config):
        """
        スクリーンショットと地震の誤マッチが発生しないことを確認.

        以前のバグ:
        - ファイル名: SHAKE-2025-12-12-190542.png（UTC 19:05）
        - 地震: 12/12 19:05 JST
        - 実際は 9 時間離れているのに同じ時刻として扱われていた
        """
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
        # 差分: 9 時間（マッチしてはいけない）
        screenshot_ts = "2025-12-12T19:05:00+00:00"

        result = manager.get_earthquake_for_screenshot(screenshot_ts, quake_db_path)

        # 9 時間離れているのでマッチしてはいけない
        assert result is None

    def test_correct_match_across_date_boundary(self, screenshot_config):
        """日付境界をまたぐケースでも正しくマッチすることを確認."""
        quake_db_path = screenshot_config.data.quake
        quake_db = QuakeDatabase(screenshot_config)

        # 地震: 2025-12-13 00:30:00 JST（= 2025-12-12 15:30:00 UTC）
        jst_earthquake = {
            "event_id": "test-quake-003",
            "detected_at": datetime(2025, 12, 13, 0, 30, 0, tzinfo=JST),
            "latitude": 35.6,
            "longitude": 139.7,
            "magnitude": 4.5,
            "depth": 50,
            "epicenter_name": "東京都",
            "max_intensity": "3",
        }
        quake_db.insert_earthquake(**jst_earthquake)

        manager = ScreenshotManager(screenshot_config)

        # スクリーンショット: 2025-12-12 15:30:00 UTC（地震と同じ瞬間、ただし日付が異なる）
        screenshot_ts = "2025-12-12T15:30:00+00:00"

        result = manager.get_earthquake_for_screenshot(screenshot_ts, quake_db_path)

        assert result is not None
        assert result["event_id"] == "test-quake-003"


class TestScreenshotFilterTimezone:
    """get_screenshots_with_earthquake_filter のタイムゾーン処理テスト."""

    def test_filter_matches_correct_earthquake(self, screenshot_config, sample_earthquake_jst):
        """地震フィルタが正しいタイムゾーンでマッチすることを確認."""
        # 地震データベースを作成
        quake_db_path = screenshot_config.data.quake
        quake_db = QuakeDatabase(screenshot_config)
        quake_db.insert_earthquake(**sample_earthquake_jst)

        # ScreenshotManager を作成してスクリーンショットをキャッシュに追加
        manager = ScreenshotManager(screenshot_config)

        # スクリーンショットのメタデータを直接キャッシュに追加
        with sqlite3.connect(manager.cache_path) as conn:
            # 地震と同じ瞬間の UTC タイムスタンプ
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
                    "2025-12-12T19:05:00+00:00",  # UTC
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
                    "2025-12-12T19:05:00+00:00",  # UTC（地震より 9 時間後）
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
