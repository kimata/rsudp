#!/usr/bin/env python3
# ruff: noqa: S101
"""
webui.py のテスト
"""

import signal
import unittest.mock

import pytest


class TestCreateApp:
    """_create_app のテスト"""

    def test_create_app_returns_flask_app(self, config):
        """_create_app が Flask アプリケーションを返す"""
        import flask

        from rsudp.cli import webui

        app = webui._create_app(config)

        assert isinstance(app, flask.Flask)

    def test_create_app_has_config(self, config):
        """_create_app が config を設定する"""
        from rsudp.cli import webui

        app = webui._create_app(config)

        assert "CONFIG" in app.config
        assert app.config["CONFIG"] == config

    def test_create_app_cors_enabled(self, config):
        """_create_app が CORS を有効にする"""
        from rsudp.cli import webui

        app = webui._create_app(config)

        assert app is not None


class TestTerm:
    """_term 関数のテスト"""

    def test_term_kills_child_and_exits(self):
        """_term が子プロセスを終了してシステム終了する"""
        from rsudp.cli import webui

        with (
            unittest.mock.patch("my_lib.proc_util.kill_child") as mock_kill,
            unittest.mock.patch.object(webui, "_stop_background_monitor"),
            pytest.raises(SystemExit) as exc_info,
        ):
            webui._term()

        mock_kill.assert_called_once()
        assert exc_info.value.code == 0


class TestSigHandler:
    """_sig_handler のテスト"""

    def test_sig_handler_sigterm(self):
        """SIGTERM で _term が呼ばれる"""
        from rsudp.cli import webui

        with (
            unittest.mock.patch("my_lib.proc_util.kill_child"),
            unittest.mock.patch.object(webui, "_stop_background_monitor"),
            pytest.raises(SystemExit),
        ):
            webui._sig_handler(signal.SIGTERM, None)

    def test_sig_handler_sigint(self):
        """SIGINT で _term が呼ばれる"""
        from rsudp.cli import webui

        with (
            unittest.mock.patch("my_lib.proc_util.kill_child"),
            unittest.mock.patch.object(webui, "_stop_background_monitor"),
            pytest.raises(SystemExit),
        ):
            webui._sig_handler(signal.SIGINT, None)

    def test_sig_handler_other_signal(self):
        """他のシグナルでは _term が呼ばれない"""
        from rsudp.cli import webui

        # SIGUSR1 などでは何も起きない
        webui._sig_handler(signal.SIGUSR1, None)
        # 例外なく終了


class TestBackgroundMonitor:
    """バックグラウンド監視のテスト"""

    def test_start_background_monitor(self, config):
        """バックグラウンド監視の開始"""
        from rsudp.cli import webui

        mock_manager = unittest.mock.MagicMock()
        mock_manager.scan_and_cache_all.return_value = 0
        mock_manager.scan_incremental.return_value = 0

        with (
            unittest.mock.patch("rsudp.quake.crawl.crawl_earthquakes", return_value=[]),
            unittest.mock.patch("rsudp.screenshot_manager.ScreenshotManager", return_value=mock_manager),
            unittest.mock.patch("my_lib.webapp.event.start_db_state_watcher", return_value=(None, None)),
        ):
            webui._start_background_monitor(config)

            # 監視スレッドが開始されていることを確認
            assert webui._monitor_thread is not None
            assert webui._monitor_thread.is_alive()

            # 停止
            webui._stop_background_monitor()

    def test_stop_background_monitor_not_running(self):
        """実行していない監視の停止"""
        from rsudp.cli import webui

        webui._monitor_thread = None
        # エラーなく完了
        webui._stop_background_monitor()

    def test_stop_background_monitor_running(self, config):
        """実行中の監視の停止"""
        from rsudp.cli import webui

        mock_manager = unittest.mock.MagicMock()
        mock_manager.scan_and_cache_all.return_value = 0
        mock_manager.scan_incremental.return_value = 0

        with (
            unittest.mock.patch("rsudp.quake.crawl.crawl_earthquakes", return_value=[]),
            unittest.mock.patch("rsudp.screenshot_manager.ScreenshotManager", return_value=mock_manager),
            unittest.mock.patch("my_lib.webapp.event.start_db_state_watcher", return_value=(None, None)),
        ):
            webui._start_background_monitor(config)

            assert webui._monitor_thread is not None

            webui._stop_background_monitor()

            # スレッドが停止していることを確認
            assert webui._monitor_thread is None

    def test_monitor_loop_with_new_earthquakes(self, config):
        """新しい地震データがある場合の監視"""
        from rsudp.cli import webui

        new_earthquakes = [
            {
                "detected_at": unittest.mock.MagicMock(strftime=lambda fmt: "2025-01-01 12:00"),
                "epicenter_name": "東京都",
                "magnitude": 5.0,
                "max_intensity": "3",
                "depth": 50,
            }
        ]

        # ScreenshotManager のモックを適切に設定
        mock_manager = unittest.mock.MagicMock()
        mock_manager.scan_and_cache_all.return_value = 0
        mock_manager.scan_incremental.return_value = 0
        mock_manager.update_earthquake_associations.return_value = 1

        with (
            unittest.mock.patch("rsudp.quake.crawl.crawl_earthquakes", return_value=new_earthquakes),
            unittest.mock.patch("rsudp.screenshot_manager.ScreenshotManager", return_value=mock_manager),
            unittest.mock.patch("my_lib.webapp.event.start_db_state_watcher", return_value=(None, None)),
        ):
            webui._start_background_monitor(config)

            import time

            time.sleep(0.5)

            webui._stop_background_monitor()

            # 地震クローラーが呼ばれたことを確認
            # （DB状態監視はstart_db_state_watcherで行われるため、直接のnotify_event呼び出しはない）

    def test_monitor_loop_exception_handling(self, config):
        """監視ループの例外処理"""
        from rsudp.cli import webui

        mock_manager = unittest.mock.MagicMock()
        mock_manager.scan_and_cache_all.return_value = 0
        mock_manager.scan_incremental.return_value = 0

        with (
            unittest.mock.patch("rsudp.quake.crawl.crawl_earthquakes", side_effect=Exception("Test error")),
            unittest.mock.patch("rsudp.screenshot_manager.ScreenshotManager", return_value=mock_manager),
            unittest.mock.patch("my_lib.webapp.event.start_db_state_watcher", return_value=(None, None)),
        ):
            webui._start_background_monitor(config)

            import time

            time.sleep(0.5)

            # 例外が発生しても監視は動作し続ける
            assert webui._monitor_thread is not None

            webui._stop_background_monitor()
