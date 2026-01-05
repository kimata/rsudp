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
        result = viewer._parse_filename("SHAKE-2025-08-12-104039.png")

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
        assert viewer._parse_filename("invalid.png") is None
        assert viewer._parse_filename("no-date.png") is None

    def test_parse_timestamp_is_utc(self):
        """タイムスタンプが UTC であることを確認."""
        result = viewer._parse_filename("SHAKE-2025-08-12-104039.png")

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


class TestImageEndpoints:
    """画像エンドポイントのテスト."""

    def test_get_image_not_found(self, flask_client):
        """存在しない画像ファイル"""
        response = flask_client.get("/rsudp/api/screenshot/image/nonexistent.png")

        assert response.status_code == 404

    def test_get_image_success(self, flask_client, config):
        """画像ファイルの取得"""
        from PIL import Image

        # テスト用の画像ファイルを作成
        screenshot_dir = config.plot.screenshot.path
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        test_file = screenshot_dir / "test-image.png"

        # 有効なPNGファイルを作成
        img = Image.new("RGB", (100, 100), color="red")
        img.save(test_file)

        response = flask_client.get("/rsudp/api/screenshot/image/test-image.png")

        assert response.status_code == 200
        assert response.content_type == "image/png"

    def test_get_image_empty_file(self, flask_client, config):
        """空の画像ファイル"""
        screenshot_dir = config.plot.screenshot.path
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        test_file = screenshot_dir / "empty.png"
        test_file.write_text("")

        response = flask_client.get("/rsudp/api/screenshot/image/empty.png")

        assert response.status_code == 404

    def test_get_ogp_image_not_found(self, flask_client):
        """存在しないOGP画像"""
        response = flask_client.get("/rsudp/api/screenshot/ogp/nonexistent.png")

        assert response.status_code == 404

    def test_get_ogp_image_success(self, flask_client, config):
        """OGP画像の取得"""
        from PIL import Image

        screenshot_dir = config.plot.screenshot.path
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        test_file = screenshot_dir / "ogp-test.png"

        # 有効なPNGファイルを作成
        img = Image.new("RGB", (800, 600), color="blue")
        img.save(test_file)

        response = flask_client.get("/rsudp/api/screenshot/ogp/ogp-test.png")

        assert response.status_code == 200
        assert response.content_type == "image/png"


class TestLatestEndpoint:
    """最新スクリーンショットエンドポイントのテスト."""

    def test_get_latest_no_screenshots(self, flask_client):
        """スクリーンショットがない場合"""
        response = flask_client.get("/rsudp/api/screenshot/latest/")

        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    def test_get_latest_success(self, flask_client, config):
        """最新スクリーンショットの取得"""
        from rsudp.screenshot_manager import ScreenshotManager

        manager = ScreenshotManager(config)

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

        response = flask_client.get("/rsudp/api/screenshot/latest/")

        assert response.status_code == 200
        data = response.get_json()
        assert data["filename"] == "SHAKE-2025-12-12-190500.png"


class TestEarthquakeCrawlEndpoint:
    """地震クロールエンドポイントのテスト."""

    def test_crawl_earthquake_data(self, flask_client):
        """地震データのクロール"""
        import unittest.mock

        with unittest.mock.patch("rsudp.quake.crawl.crawl_earthquakes", return_value=[]):
            response = flask_client.post("/rsudp/api/earthquake/crawl/")

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True


class TestCleanEndpoint:
    """クリーンエンドポイントのテスト."""

    def test_clean_dry_run(self, flask_client):
        """dry-run モードでのクリーン"""
        import unittest.mock

        with unittest.mock.patch("cleaner.get_screenshots_to_clean", return_value=[]):
            response = flask_client.post(
                "/rsudp/api/screenshot/clean/",
                json={"dry_run": True},
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert data["dry_run"] is True

    def test_clean_execute(self, flask_client):
        """実際のクリーン実行"""
        import unittest.mock

        with (
            unittest.mock.patch("cleaner.get_screenshots_to_clean", return_value=[]),
            unittest.mock.patch("cleaner.delete_screenshots", return_value=0),
        ):
            response = flask_client.post(
                "/rsudp/api/screenshot/clean/",
                json={"dry_run": False},
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert data["dry_run"] is False


class TestDateEndpoints:
    """日付エンドポイントのテスト."""

    def test_months_endpoint(self, flask_client, config):
        """月一覧エンドポイント"""
        from rsudp.screenshot_manager import ScreenshotManager

        manager = ScreenshotManager(config)

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

        response = flask_client.get("/rsudp/api/screenshot/2025/months/")

        assert response.status_code == 200
        data = response.get_json()
        assert "months" in data

    def test_days_endpoint(self, flask_client, config):
        """日一覧エンドポイント"""
        from rsudp.screenshot_manager import ScreenshotManager

        manager = ScreenshotManager(config)

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

        response = flask_client.get("/rsudp/api/screenshot/2025/12/days/")

        assert response.status_code == 200
        data = response.get_json()
        assert "days" in data

    def test_by_date_endpoint(self, flask_client, config):
        """日付別スクリーンショットエンドポイント"""
        from rsudp.screenshot_manager import ScreenshotManager

        manager = ScreenshotManager(config)

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

        response = flask_client.get("/rsudp/api/screenshot/2025/12/12/")

        assert response.status_code == 200
        data = response.get_json()
        assert "screenshots" in data


class TestOgpFunctions:
    """OGP関連関数のテスト."""

    def test_build_ogp_meta_tags(self):
        """OGPメタタグの構築"""
        result = viewer._build_ogp_meta_tags(
            title="Test Title",
            description="Test Description",
            image_url="https://example.com/image.png",
            page_url="https://example.com/",
        )

        assert "Test Title" in result
        assert "Test Description" in result
        assert "https://example.com/image.png" in result
        assert "og:title" in result
        assert "twitter:card" in result

    def test_build_ogp_meta_tags_without_image(self):
        """画像なしのOGPメタタグ"""
        result = viewer._build_ogp_meta_tags(
            title="Test Title",
            description="Test Description",
            image_url="",
            page_url="https://example.com/",
        )

        assert "Test Title" in result
        assert "og:image" not in result

    def test_generate_ogp_meta_tags_default(self):
        """デフォルトのOGPメタタグ生成"""
        result = viewer._generate_ogp_meta_tags(None, "https://example.com")

        assert "RSUDP スクリーンショットビューア" in result

    def test_generate_ogp_meta_tags_with_filename(self, flask_app, config):
        """ファイル名指定のOGPメタタグ生成"""
        import unittest.mock

        with (
            flask_app.app_context(),
            unittest.mock.patch.object(
                viewer,
                "_get_ogp_content_for_screenshot",
                return_value=("", "", "", ""),
            ),
        ):
            result = viewer._generate_ogp_meta_tags("SHAKE-2025-12-12-190500.png", "https://example.com")

            # デフォルト値が使われる
            assert "RSUDP スクリーンショットビューア" in result


class TestIndexWithOgp:
    """index_with_ogp のテスト."""

    def test_index_static_dir_not_configured(self, flask_client):
        """静的ディレクトリが設定されていない場合"""
        import my_lib.webapp.config

        original = my_lib.webapp.config.STATIC_DIR_PATH
        my_lib.webapp.config.STATIC_DIR_PATH = None

        try:
            response = flask_client.get("/rsudp/")
            assert response.status_code == 500
        finally:
            my_lib.webapp.config.STATIC_DIR_PATH = original

    def test_index_html_not_found(self, flask_client, config):
        """index.html が見つからない場合"""
        import my_lib.webapp.config

        original = my_lib.webapp.config.STATIC_DIR_PATH
        my_lib.webapp.config.STATIC_DIR_PATH = config.webapp.static_dir_path

        # 静的ディレクトリは存在するがindex.htmlがない
        config.webapp.static_dir_path.mkdir(parents=True, exist_ok=True)

        try:
            response = flask_client.get("/rsudp/")
            assert response.status_code == 404
        finally:
            my_lib.webapp.config.STATIC_DIR_PATH = original

    def test_index_success(self, flask_client, config):
        """index.html の正常取得"""
        import my_lib.webapp.config

        original = my_lib.webapp.config.STATIC_DIR_PATH
        my_lib.webapp.config.STATIC_DIR_PATH = config.webapp.static_dir_path

        # 静的ディレクトリとindex.htmlを作成
        config.webapp.static_dir_path.mkdir(parents=True, exist_ok=True)
        index_file = config.webapp.static_dir_path / "index.html"
        index_file.write_text("<html><head></head><body>Test</body></html>")

        try:
            response = flask_client.get("/rsudp/")
            assert response.status_code == 200
            assert b"og:title" in response.data
        finally:
            my_lib.webapp.config.STATIC_DIR_PATH = original
