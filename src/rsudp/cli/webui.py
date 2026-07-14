#!/usr/bin/env python3
"""
rsudp のプロットデータを表示する Web UI サーバです。

Usage:
  rsudp-webui [-c CONFIG] [-p PORT] [-D]

Options:
  -c CONFIG         : 通常モードで使う設定ファイルを指定します。[default: config.yaml]
  -p PORT           : WEB サーバのポートを指定します。[default: 5000]
  -D                : デバッグモードで動作します。
"""

import logging
import pathlib

import flask
import flask_cors
import my_lib.config
import my_lib.webapp.event
import my_lib.webapp.runner

import rsudp.config
import rsudp.monitor

_SCHEMA_CONFIG = "schema/config.schema"

# バックグラウンド監視インスタンス（_app_factory() で初期化）
_background_monitor: rsudp.monitor.BackgroundMonitor | None = None

_URL_PREFIX = "/rsudp"


def _create_app(config: rsudp.config.Config):
    # NOTE: 関数内 import は my_lib をローカル変数にするため、モジュールレベルの
    # my_lib.* 参照より先にまとめて行う
    import my_lib.webapp.config

    # NOTE: アクセスログは無効にする
    my_lib.webapp.runner.silence_werkzeug_log()

    # Config.__post_init__ で絶対パスであることが保証されている
    webapp_config = my_lib.webapp.config.WebappConfig(static_dir_path=config.webapp.static_dir_path)
    environment = my_lib.webapp.config.build_environment(webapp_config, url_prefix=_URL_PREFIX)

    import my_lib.webapp.base
    import my_lib.webapp.util

    import rsudp.webui.api.viewer

    app = flask.Flask(__name__)

    flask_cors.CORS(app)

    app.config["CONFIG"] = config

    # OGPルートを優先するため、viewer blueprintを先に登録
    app.register_blueprint(rsudp.webui.api.viewer.blueprint)
    app.register_blueprint(
        my_lib.webapp.base.create_static_blueprint(environment=environment),
        url_prefix=_URL_PREFIX,
    )
    app.register_blueprint(my_lib.webapp.base.create_root_redirect_blueprint(url_prefix=_URL_PREFIX))
    app.register_blueprint(my_lib.webapp.util.blueprint, url_prefix=_URL_PREFIX)
    # SSE イベント通知用エンドポイント
    app.register_blueprint(my_lib.webapp.event.blueprint, url_prefix=_URL_PREFIX)

    my_lib.webapp.config.show_handler_list(app)

    return app


def _load_config(config_file, args):
    config_dict = my_lib.config.load(config_file, pathlib.Path(_SCHEMA_CONFIG))
    return rsudp.config.load_from_dict(config_dict, pathlib.Path.cwd())


def _app_factory(config, ctx):
    app = _create_app(config)

    # バックグラウンド監視はリローダーの子プロセスでのみ開始する（二重起動の防止）
    if my_lib.webapp.runner.should_init(ctx.use_reloader):
        monitor = rsudp.monitor.BackgroundMonitor(config)
        monitor.start()
        global _background_monitor
        _background_monitor = monitor

    return app


def _stop_monitor():
    if _background_monitor is not None:
        logging.info("Stopping background monitor...")
        _background_monitor.stop()


SPEC = my_lib.webapp.runner.WebAppSpec(
    logger_name="rsudp",
    config_loader=_load_config,
    app_factory=_app_factory,
    term_hooks=(_stop_monitor,),
)


def main() -> None:
    """Console script entry point."""
    assert __doc__ is not None  # noqa: S101 - type narrowing for pyright
    my_lib.webapp.runner.run(SPEC, __doc__)


if __name__ == "__main__":
    main()
