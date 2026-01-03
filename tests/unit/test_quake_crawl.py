# ruff: noqa: S101
"""
QuakeCrawler のユニットテスト.

気象庁地震情報クローラーの基本機能をテストします。
"""

import zoneinfo
from unittest.mock import MagicMock, patch

import pytest

from rsudp.quake import crawl

JST = zoneinfo.ZoneInfo("Asia/Tokyo")


class TestParseCoordinate:
    """座標パースのテスト."""

    def test_parse_normal_coordinate(self):
        """通常の座標文字列をパースできることを確認."""
        coord_str = "+35.6+139.7-50000/"
        lat, lon, depth = crawl.parse_coordinate(coord_str)

        assert lat == 35.6
        assert lon == 139.7
        assert depth == 50  # メートルからキロメートルに変換

    def test_parse_negative_latitude(self):
        """南緯の座標をパースできることを確認."""
        coord_str = "-35.6+139.7-10000/"
        lat, lon, depth = crawl.parse_coordinate(coord_str)

        assert lat == -35.6
        assert lon == 139.7
        assert depth == 10

    def test_parse_negative_longitude(self):
        """西経の座標をパースできることを確認."""
        coord_str = "+35.6-139.7-10000/"
        lat, lon, depth = crawl.parse_coordinate(coord_str)

        assert lat == 35.6
        assert lon == -139.7
        assert depth == 10

    def test_parse_invalid_coordinate_raises_error(self):
        """無効な座標文字列でエラーが発生することを確認."""
        with pytest.raises(crawl.InvalidCoordinateError):
            crawl.parse_coordinate("invalid")


class TestParseIntensity:
    """震度パースのテスト."""

    def test_parse_intensity_1_to_4(self):
        """震度 1〜4 が正しくパースされることを確認."""
        assert crawl.parse_intensity("1") == 1
        assert crawl.parse_intensity("2") == 2
        assert crawl.parse_intensity("3") == 3
        assert crawl.parse_intensity("4") == 4

    def test_parse_intensity_5_weak_strong(self):
        """震度 5弱・5強 が正しくパースされることを確認."""
        assert crawl.parse_intensity("5-") == 50
        assert crawl.parse_intensity("5+") == 55

    def test_parse_intensity_6_weak_strong(self):
        """震度 6弱・6強 が正しくパースされることを確認."""
        assert crawl.parse_intensity("6-") == 60
        assert crawl.parse_intensity("6+") == 65

    def test_parse_intensity_7(self):
        """震度 7 が正しくパースされることを確認."""
        assert crawl.parse_intensity("7") == 7

    def test_parse_intensity_unknown(self):
        """不明な震度で 0 が返されることを確認."""
        assert crawl.parse_intensity("unknown") == 0
        assert crawl.parse_intensity("") == 0


class TestQuakeCrawlerInit:
    """QuakeCrawler 初期化のテスト."""

    def test_init(self, temp_dir):
        """QuakeCrawler が正しく初期化されることを確認."""
        config = {"data": {"quake": str(temp_dir / "test.db")}}
        crawler = crawl.QuakeCrawler(config)

        assert crawler.config == config
        assert crawler.db is not None
        assert crawler.session is not None


class TestFetchEarthquakeList:
    """地震一覧取得のテスト."""

    def test_fetch_earthquake_list_success(self, temp_dir):
        """地震一覧を正常に取得できることを確認."""
        config = {"data": {"quake": str(temp_dir / "test.db")}}
        crawler = crawl.QuakeCrawler(config)

        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"eid": "quake-001", "maxi": "3", "json": "quake001.json"},
            {"eid": "quake-002", "maxi": "4", "json": "quake002.json"},
        ]
        mock_response.raise_for_status = MagicMock()

        with patch.object(crawler.session, "get", return_value=mock_response):
            result = crawler.fetch_earthquake_list()

        assert len(result) == 2
        assert result[0]["eid"] == "quake-001"

    def test_fetch_earthquake_list_error(self, temp_dir):
        """API エラー時に空のリストが返されることを確認."""
        import requests

        config = {"data": {"quake": str(temp_dir / "test.db")}}
        crawler = crawl.QuakeCrawler(config)

        with patch.object(crawler.session, "get", side_effect=requests.RequestException("Network error")):
            result = crawler.fetch_earthquake_list()

        assert result == []


class TestFetchEarthquakeDetail:
    """地震詳細取得のテスト."""

    def test_fetch_earthquake_detail_success(self, temp_dir):
        """地震詳細を正常に取得できることを確認."""
        config = {"data": {"quake": str(temp_dir / "test.db")}}
        crawler = crawl.QuakeCrawler(config)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Body": {
                "Earthquake": {
                    "OriginTime": "2025-12-12T19:05:00+09:00",
                    "Hypocenter": {"Area": {"Coordinate": "+35.6+139.7-50000/", "Name": "東京都"}},
                    "Magnitude": 4.5,
                }
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(crawler.session, "get", return_value=mock_response):
            result = crawler.fetch_earthquake_detail("quake001.json")

        assert result is not None
        assert result["Body"]["Earthquake"]["Magnitude"] == 4.5

    def test_fetch_earthquake_detail_error(self, temp_dir):
        """API エラー時に None が返されることを確認."""
        import requests

        config = {"data": {"quake": str(temp_dir / "test.db")}}
        crawler = crawl.QuakeCrawler(config)

        with patch.object(crawler.session, "get", side_effect=requests.RequestException("Network error")):
            result = crawler.fetch_earthquake_detail("quake001.json")

        assert result is None


class TestCrawlAndStore:
    """地震データ収集・保存のテスト."""

    def test_crawl_and_store_filters_by_intensity(self, temp_dir):
        """min_intensity でフィルタリングされることを確認."""
        config = {"data": {"quake": str(temp_dir / "test.db")}}
        crawler = crawl.QuakeCrawler(config)

        # 震度 2（min_intensity=3 未満）
        mock_list = [{"eid": "quake-001", "maxi": "2", "json": "quake001.json"}]

        with patch.object(crawler, "fetch_earthquake_list", return_value=mock_list):
            result = crawler.crawl_and_store(min_intensity=3)

        # 震度が閾値未満なのでスキップ
        assert result == []
