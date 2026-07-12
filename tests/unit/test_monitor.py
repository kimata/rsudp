# ruff: noqa: S101
"""
BackgroundMonitor の Slack 通知のユニットテスト.

info チャンネル設定時に地震検出・JMA 照合通知が送られることを確認します。
"""

import datetime
import sqlite3
import unittest.mock

import my_lib.notify.slack
import pytest

import rsudp.config
import rsudp.monitor
import rsudp.types
from rsudp.quake.database import QuakeDatabase
from rsudp.screenshot_manager import ScreenshotManager
from tests.helpers import insert_screenshot_metadata, insert_test_earthquake


def _slack_error_info_config() -> my_lib.notify.slack.SlackErrorInfoConfig:
    """info チャンネル付きの Slack 設定を構築する（channel id は None）."""
    return my_lib.notify.slack.SlackErrorInfoConfig(
        bot_token="xoxb-test",  # noqa: S106 - テスト用ダミートークン
        from_name="test",
        info=my_lib.notify.slack.SlackInfoConfig(
            channel=my_lib.notify.slack.SlackChannelConfig(name="info", id=None),
        ),
        error=my_lib.notify.slack.SlackErrorConfig(
            channel=my_lib.notify.slack.SlackChannelConfig(name="error", id="C-ERR"),
            interval_min=0,
        ),
    )


@pytest.fixture
def monitor_config(temp_dir):
    """info チャンネル付き Slack 設定を含むテスト用 Config."""
    screenshot_dir = temp_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    return rsudp.config.Config(
        plot=rsudp.config.PlotConfig(
            screenshot=rsudp.config.ScreenshotConfig(path=screenshot_dir),
        ),
        data=rsudp.config.DataConfig(
            cache=temp_dir / "cache.db",
            quake=temp_dir / "quake.db",
            selenium=temp_dir / "selenium",
        ),
        webapp=rsudp.config.WebappConfig(
            static_dir_path=temp_dir / "static",
        ),
        slack=_slack_error_info_config(),
        base_dir=temp_dir,
    )


class TestNotifyMatchedEarthquakes:
    """JMA 照合つき確定通知のテスト."""

    def test_notify_when_matched(self, monitor_config):
        """自局スクショと照合が取れた新規地震は info 通知される."""
        quake_db = QuakeDatabase(monitor_config)
        insert_test_earthquake(
            quake_db,
            event_id="test-quake-001",
            detected_at=datetime.datetime(2025, 12, 13, 4, 5, 0, tzinfo=rsudp.types.JST),
            epicenter_name="東京都",
            max_intensity="3",
        )

        manager = ScreenshotManager(monitor_config)
        with sqlite3.connect(manager.cache_path) as conn:
            insert_screenshot_metadata(conn, earthquake_event_id="test-quake-001")

        monitor = rsudp.monitor.BackgroundMonitor(monitor_config)
        new_earthquakes = [
            {
                "event_id": "test-quake-001",
                "detected_at": datetime.datetime(2025, 12, 13, 4, 5, 0, tzinfo=rsudp.types.JST),
                "epicenter_name": "東京都",
                "magnitude": 4.5,
                "max_intensity": "3",
                "depth": 50,
            }
        ]

        with unittest.mock.patch.object(my_lib.notify.slack, "info") as mock_info:
            monitor._notify_matched_earthquakes(new_earthquakes)

        mock_info.assert_called_once()

    def test_no_notify_when_unmatched(self, monitor_config):
        """自局で検出していない新規地震は通知されない."""
        QuakeDatabase(monitor_config)
        ScreenshotManager(monitor_config)  # 空キャッシュを作成

        monitor = rsudp.monitor.BackgroundMonitor(monitor_config)
        new_earthquakes = [
            {
                "event_id": "far-quake-999",
                "detected_at": datetime.datetime(2025, 12, 13, 4, 5, 0, tzinfo=rsudp.types.JST),
                "epicenter_name": "遠地",
                "magnitude": 4.5,
                "max_intensity": "3",
                "depth": 50,
            }
        ]

        with unittest.mock.patch.object(my_lib.notify.slack, "info") as mock_info:
            monitor._notify_matched_earthquakes(new_earthquakes)

        mock_info.assert_not_called()


class TestNotifyDetection:
    """地震検出時の通知のテスト."""

    def test_notify_detection_representative(self, monitor_config):
        """増分スキャンの代表スクショが info 通知される."""
        manager = ScreenshotManager(monitor_config)
        with sqlite3.connect(manager.cache_path) as conn:
            insert_screenshot_metadata(conn, filename="SHAKE-2025-12-12-190500.png", max_count=1234.0)
        # 直近スキャンで追加されたファイルを模擬
        manager._last_scanned_files = ["SHAKE-2025-12-12-190500.png"]

        monitor = rsudp.monitor.BackgroundMonitor(monitor_config)

        with unittest.mock.patch.object(my_lib.notify.slack, "info") as mock_info:
            monitor._notify_detection(manager)

        mock_info.assert_called_once()
        # メッセージに MaxCount が含まれる
        args = mock_info.call_args.args
        assert "MaxCount=1234" in args[2]


class TestNotifyDisabled:
    """info チャンネルが無い設定では通知しないことのテスト."""

    def test_empty_slack_no_error(self, screenshot_config):
        """SlackEmptyConfig（デフォルト）でも例外なく no-op で完了する."""
        manager = ScreenshotManager(screenshot_config)
        with sqlite3.connect(manager.cache_path) as conn:
            insert_screenshot_metadata(conn)
        manager._last_scanned_files = ["SHAKE-2025-12-12-190500.png"]

        monitor = rsudp.monitor.BackgroundMonitor(screenshot_config)

        # 例外が発生しないことを確認
        monitor._notify_detection(manager)
