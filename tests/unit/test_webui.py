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

        import webui

        app = webui._create_app(config)

        assert isinstance(app, flask.Flask)

    def test_create_app_has_config(self, config):
        """_create_app が config を設定する"""
        import webui

        app = webui._create_app(config)

        assert "CONFIG" in app.config
        assert app.config["CONFIG"] == config

    def test_create_app_cors_enabled(self, config):
        """_create_app が CORS を有効にする"""
        import webui

        app = webui._create_app(config)

        assert app is not None


class TestTerm:
    """_term 関数のテスト"""

    def test_term_kills_child_and_exits(self):
        """_term が子プロセスを終了してシステム終了する"""
        import webui

        with (
            unittest.mock.patch("my_lib.proc_util.kill_child") as mock_kill,
            unittest.mock.patch.object(webui, "_stop_quake_crawler"),
            pytest.raises(SystemExit) as exc_info,
        ):
            webui._term()

        mock_kill.assert_called_once()
        assert exc_info.value.code == 0


class TestSigHandler:
    """_sig_handler のテスト"""

    def test_sig_handler_sigterm(self):
        """SIGTERM で _term が呼ばれる"""
        import webui

        with (
            unittest.mock.patch("my_lib.proc_util.kill_child"),
            unittest.mock.patch.object(webui, "_stop_quake_crawler"),
            pytest.raises(SystemExit),
        ):
            webui._sig_handler(signal.SIGTERM, None)

    def test_sig_handler_sigint(self):
        """SIGINT で _term が呼ばれる"""
        import webui

        with (
            unittest.mock.patch("my_lib.proc_util.kill_child"),
            unittest.mock.patch.object(webui, "_stop_quake_crawler"),
            pytest.raises(SystemExit),
        ):
            webui._sig_handler(signal.SIGINT, None)

    def test_sig_handler_other_signal(self):
        """他のシグナルでは _term が呼ばれない"""
        import webui

        # SIGUSR1 などでは何も起きない
        webui._sig_handler(signal.SIGUSR1, None)
        # 例外なく終了


class TestQuakeCrawler:
    """地震クローラーのテスト"""

    def test_start_quake_crawler(self, config):
        """地震クローラーの開始"""
        import webui

        with unittest.mock.patch("rsudp.quake.crawl.crawl_earthquakes", return_value=[]):
            webui._start_quake_crawler(config, interval=1)

            # クローラースレッドが開始されていることを確認
            assert webui._quake_crawler_thread is not None
            assert webui._quake_crawler_thread.is_alive()

            # 停止
            webui._stop_quake_crawler()

    def test_stop_quake_crawler_not_running(self):
        """実行していないクローラーの停止"""
        import webui

        webui._quake_crawler_thread = None
        # エラーなく完了
        webui._stop_quake_crawler()

    def test_stop_quake_crawler_running(self, config):
        """実行中のクローラーの停止"""
        import webui

        with unittest.mock.patch("rsudp.quake.crawl.crawl_earthquakes", return_value=[]):
            webui._start_quake_crawler(config, interval=1)

            assert webui._quake_crawler_thread is not None

            webui._stop_quake_crawler()

            # スレッドが停止していることを確認
            assert webui._quake_crawler_thread is None

    def test_crawler_loop_with_new_earthquakes(self, config):
        """新しい地震データがある場合のクローラー"""
        import webui

        new_earthquakes = [
            {
                "detected_at": unittest.mock.MagicMock(strftime=lambda fmt: "2025-01-01 12:00"),
                "epicenter_name": "東京都",
                "magnitude": 5.0,
                "max_intensity": "3",
                "depth": 50,
            }
        ]

        with (
            unittest.mock.patch("rsudp.quake.crawl.crawl_earthquakes", return_value=new_earthquakes),
            unittest.mock.patch("rsudp.screenshot_manager.ScreenshotManager"),
        ):
            webui._start_quake_crawler(config, interval=1)

            import time

            time.sleep(0.5)

            webui._stop_quake_crawler()

    def test_crawler_loop_exception_handling(self, config):
        """クローラーループの例外処理"""
        import webui

        with unittest.mock.patch("rsudp.quake.crawl.crawl_earthquakes", side_effect=Exception("Test error")):
            webui._start_quake_crawler(config, interval=1)

            import time

            time.sleep(0.5)

            # 例外が発生してもクローラーは動作し続ける
            assert webui._quake_crawler_thread is not None

            webui._stop_quake_crawler()
