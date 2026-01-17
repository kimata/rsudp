# ruff: noqa: S101
"""
WebUI 統合テスト.

Flask アプリケーションの統合テストを実行します。
"""

import sqlite3
import zoneinfo
from datetime import datetime

from rsudp.quake.database import QuakeDatabase
from rsudp.screenshot_manager import ScreenshotManager

JST = zoneinfo.ZoneInfo("Asia/Tokyo")


class TestFlaskAppIntegration:
    """Flask アプリケーション統合テスト."""

    def test_app_starts(self, flask_app):
        """アプリケーションが正常に起動することを確認."""
        assert flask_app is not None
        assert flask_app.config["TESTING"] is True

    def test_client_works(self, flask_client):
        """テストクライアントが動作することを確認."""
        response = flask_client.get("/rsudp/api/screenshot/")
        assert response.status_code == 200


class TestScreenshotAndEarthquakeIntegration:
    """スクリーンショットと地震データの統合テスト."""

    def test_earthquake_filter_integration(self, config, temp_dir):
        """地震フィルタが正しく動作することを確認."""
        # 地震データを挿入
        quake_db = QuakeDatabase(config)
        quake_db.insert_earthquake(
            event_id="test-quake-001",
            detected_at=datetime(2025, 12, 13, 4, 5, 0, tzinfo=JST),
            latitude=35.6,
            longitude=139.7,
            magnitude=4.5,
            depth=50,
            epicenter_name="東京都",
            max_intensity="3",
        )

        # スクリーンショットマネージャーを作成
        manager = ScreenshotManager(config)

        # キャッシュにスクリーンショットを追加（地震と同じ時刻）
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
                    "2025-12-12T19:05:00+00:00",  # 地震と同じ瞬間（UTC）
                    100.0,
                    50.0,
                    2.0,
                    1000.0,
                    1234567890.0,
                    12345,
                    "STA=100.0, LTA=50.0",
                ),
            )

        # 地震フィルタでスクリーンショットを取得
        quake_db_path = config.data.quake
        result = manager.get_screenshots_with_earthquake_filter(quake_db_path=quake_db_path)

        # マッチすることを確認
        assert len(result) == 1
        assert result[0]["earthquake"]["event_id"] == "test-quake-001"

    def test_no_earthquake_filter_integration(self, config, temp_dir):
        """地震フィルタなしでスクリーンショットを取得できることを確認."""
        manager = ScreenshotManager(config)

        # キャッシュにスクリーンショットを追加
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

        # 全スクリーンショットを取得（フィルタなし）
        result = manager.get_screenshots_with_signal_filter()

        assert len(result) == 1


class TestApiFlowIntegration:
    """API フロー統合テスト."""

    def test_full_api_flow(self, flask_client, config):
        """API の一連のフローが正常に動作することを確認."""
        # 1. 統計情報を取得
        response = flask_client.get("/rsudp/api/screenshot/statistics/")
        assert response.status_code == 200
        stats = response.get_json()
        assert "total" in stats

        # 2. スクリーンショット一覧を取得
        response = flask_client.get("/rsudp/api/screenshot/")
        assert response.status_code == 200
        screenshots = response.get_json()
        assert "screenshots" in screenshots

        # 3. 年一覧を取得
        response = flask_client.get("/rsudp/api/screenshot/years/")
        assert response.status_code == 200
        years = response.get_json()
        assert "years" in years

        # 4. 地震一覧を取得
        response = flask_client.get("/rsudp/api/earthquake/list/")
        assert response.status_code == 200
        earthquakes = response.get_json()
        assert "earthquakes" in earthquakes

    def test_scan_and_list_flow(self, flask_client):
        """スキャンと一覧取得のフローが正常に動作することを確認."""
        # 1. スキャンを実行
        response = flask_client.post("/rsudp/api/screenshot/scan/")
        assert response.status_code == 200

        # 2. スクリーンショット一覧を取得
        response = flask_client.get("/rsudp/api/screenshot/")
        assert response.status_code == 200


class TestTimezoneIntegration:
    """タイムゾーン統合テスト."""

    def test_timezone_correct_match(self, config, temp_dir):
        """UTC と JST の正しいマッチングを確認."""
        # 地震データを挿入（JST）
        quake_db = QuakeDatabase(config)
        quake_db.insert_earthquake(
            event_id="tz-test-001",
            detected_at=datetime(2025, 12, 13, 4, 5, 0, tzinfo=JST),  # JST
            latitude=35.6,
            longitude=139.7,
            magnitude=4.5,
            depth=50,
            epicenter_name="東京都",
            max_intensity="3",
        )

        manager = ScreenshotManager(config)

        # UTC で検索（同じ瞬間）
        # 2025-12-13 04:05:00 JST = 2025-12-12 19:05:00 UTC
        screenshot_ts = "2025-12-12T19:05:00+00:00"
        quake_db_path = config.data.quake

        result = manager.get_earthquake_for_screenshot(screenshot_ts, quake_db_path)

        assert result is not None
        assert result.event_id == "tz-test-001"

    def test_timezone_no_false_match(self, config, temp_dir):
        """UTC と JST の誤マッチが発生しないことを確認."""
        # 地震データを挿入（JST で 19:05）
        quake_db = QuakeDatabase(config)
        quake_db.insert_earthquake(
            event_id="tz-test-002",
            detected_at=datetime(2025, 12, 12, 19, 5, 0, tzinfo=JST),  # JST
            latitude=35.6,
            longitude=139.7,
            magnitude=4.5,
            depth=50,
            epicenter_name="東京都",
            max_intensity="3",
        )

        manager = ScreenshotManager(config)

        # UTC で 19:05（JST では翌日 04:05、つまり 9 時間後）
        screenshot_ts = "2025-12-12T19:05:00+00:00"
        quake_db_path = config.data.quake

        result = manager.get_earthquake_for_screenshot(screenshot_ts, quake_db_path)

        # 9 時間離れているのでマッチしてはいけない
        assert result is None
