# ruff: noqa: S101
"""
Viewer API のユニットテスト.

REST API エンドポイントの基本機能をテストします。
"""

import sqlite3
import zoneinfo

from rsudp.webui.api import viewer

JST = zoneinfo.ZoneInfo("Asia/Tokyo")


class TestParseFilename:
    """ファイル名解析のテスト."""

    def test_parse_valid_filename(self):
        """有効なファイル名が正しくパースされることを確認."""
        result = viewer.parse_filename("SHAKE-2025-08-12-104039.png")

        assert result is not None
        assert result["prefix"] == "SHAKE"
        assert result["year"] == 2025
        assert result["month"] == 8
        assert result["day"] == 12
        assert result["hour"] == 10
        assert result["minute"] == 40
        assert result["second"] == 39

    def test_parse_invalid_filename(self):
        """無効なファイル名で None が返されることを確認."""
        assert viewer.parse_filename("invalid.png") is None
        assert viewer.parse_filename("no-date.png") is None

    def test_parse_timestamp_is_utc(self):
        """タイムスタンプが UTC であることを確認."""
        result = viewer.parse_filename("SHAKE-2025-08-12-104039.png")

        assert result is not None
        assert "+00:00" in result["timestamp"]


class TestApiEndpoints:
    """API エンドポイントのテスト."""

    def test_years_endpoint(self, flask_client, screenshot_config, temp_dir):
        """年一覧 API が動作することを確認."""
        # キャッシュにデータを追加
        from rsudp.screenshot_manager import ScreenshotManager

        manager = ScreenshotManager(screenshot_config)

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

        response = flask_client.get("/rsudp/api/screenshot/years/")

        assert response.status_code == 200
        data = response.get_json()
        assert "years" in data

    def test_statistics_endpoint(self, flask_client):
        """統計情報 API が動作することを確認."""
        response = flask_client.get("/rsudp/api/screenshot/statistics/")

        assert response.status_code == 200
        data = response.get_json()
        assert "total" in data

    def test_screenshot_list_endpoint(self, flask_client):
        """スクリーンショット一覧 API が動作することを確認."""
        response = flask_client.get("/rsudp/api/screenshot/")

        assert response.status_code == 200
        data = response.get_json()
        assert "screenshots" in data
        assert "total" in data

    def test_earthquake_list_endpoint(self, flask_client):
        """地震一覧 API が動作することを確認."""
        response = flask_client.get("/rsudp/api/earthquake/list/")

        assert response.status_code == 200
        data = response.get_json()
        assert "earthquakes" in data

    def test_scan_endpoint(self, flask_client):
        """スキャン API が動作することを確認."""
        response = flask_client.post("/rsudp/api/screenshot/scan/")

        assert response.status_code == 200
        data = response.get_json()
        assert "success" in data


class TestQueryParameters:
    """クエリパラメータのテスト."""

    def test_min_max_signal_filter(self, flask_client):
        """min_max_signal パラメータが機能することを確認."""
        response = flask_client.get("/rsudp/api/screenshot/?min_max_signal=1000")

        assert response.status_code == 200
        data = response.get_json()
        assert "screenshots" in data

    def test_earthquake_only_filter(self, flask_client):
        """earthquake_only パラメータが機能することを確認."""
        response = flask_client.get("/rsudp/api/screenshot/?earthquake_only=true")

        assert response.status_code == 200
        data = response.get_json()
        assert "screenshots" in data


class TestStatisticsWithEarthquakeFilter:
    """地震フィルタ付き統計のテスト."""

    def test_statistics_with_earthquake_only_true(self, flask_client):
        """earthquake_only=true で統計が取得できることを確認."""
        response = flask_client.get("/rsudp/api/screenshot/statistics/?earthquake_only=true")

        assert response.status_code == 200
        data = response.get_json()
        assert "total" in data
        assert "absolute_total" in data

    def test_statistics_with_earthquake_only_false(self, flask_client):
        """earthquake_only=false で統計が取得できることを確認."""
        response = flask_client.get("/rsudp/api/screenshot/statistics/?earthquake_only=false")

        assert response.status_code == 200
        data = response.get_json()
        assert "total" in data
