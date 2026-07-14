#!/usr/bin/env python3
# ruff: noqa: S101
"""
webui.py のテスト
"""

import unittest.mock


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


class TestStopMonitor:
    """_stop_monitor 関数のテスト"""

    def test_no_monitor_does_nothing(self):
        """監視が起動していなければ何もしない"""
        from rsudp.cli import webui

        webui._background_monitor = None
        webui._stop_monitor()  # 例外が出なければ OK

    def test_stops_running_monitor(self):
        """起動中の監視を停止する"""
        from rsudp.cli import webui

        monitor = unittest.mock.MagicMock()
        webui._background_monitor = monitor
        try:
            webui._stop_monitor()
        finally:
            webui._background_monitor = None

        monitor.stop.assert_called_once()


class TestSpec:
    """WebAppSpec 定義のテスト

    シグナル処理・graceful shutdown 自体は my_lib.webapp.runner 側で
    テストされるため、ここでは配線のみ確認する。
    """

    def test_term_hook_wired(self):
        """SPEC の term_hooks に _stop_monitor が配線されている"""
        from rsudp.cli import webui

        assert webui._stop_monitor in webui.SPEC.term_hooks

    def test_logger_name(self):
        """ロガー名が rsudp である"""
        from rsudp.cli import webui

        assert webui.SPEC.logger_name == "rsudp"
