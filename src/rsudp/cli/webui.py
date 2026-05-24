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
import os
import pathlib
import signal
import sys

import flask
import flask_cors
import my_lib.config
import my_lib.logger
import my_lib.proc_util
import my_lib.webapp.event

import rsudp.config
import rsudp.monitor

_SCHEMA_CONFIG = "schema/config.schema"

# バックグラウンド監視インスタンス（main() で初期化）
_background_monitor: rsudp.monitor.BackgroundMonitor | None = None


def _term():
    # バックグラウンド監視を停止
    if _background_monitor is not None:
        _background_monitor.stop()

    # 子プロセスを終了
    my_lib.proc_util.kill_child()

    # プロセス終了
    logging.info("Graceful shutdown completed")
    sys.exit(0)


def _sig_handler(num, frame):
    logging.warning("receive signal %d", num)

    if num in (signal.SIGTERM, signal.SIGINT):
        _term()


_URL_PREFIX = "/rsudp"


def _create_app(config: rsudp.config.Config):
    # NOTE: アクセスログは無効にする
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    import my_lib.webapp.config

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


def main() -> None:
    """Console script entry point."""
    import atexit
    import contextlib

    import docopt

    assert __doc__ is not None  # noqa: S101 - type narrowing for pyright
    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    port = args["-p"]
    debug_mode = args["-D"]

    my_lib.logger.init("rsudp", level=logging.DEBUG if debug_mode else logging.INFO)

    config_dict = my_lib.config.load(config_file, pathlib.Path(_SCHEMA_CONFIG))
    config = rsudp.config.load_from_dict(config_dict, pathlib.Path.cwd())

    app = _create_app(config)

    # プロセスグループリーダーとして実行（リローダープロセスの適切な管理のため）
    with contextlib.suppress(PermissionError):
        os.setpgrp()

    # 異常終了時のクリーンアップ処理を登録
    def cleanup_on_exit():
        try:
            current_pid = os.getpid()
            pgid = os.getpgid(current_pid)
            if current_pid == pgid:
                # プロセスグループ内の他のプロセスを終了
                os.killpg(pgid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass

    atexit.register(cleanup_on_exit)

    # Enhanced signal handler for process group management
    def enhanced_sig_handler(num, frame):
        logging.warning("receive signal %d", num)

        if num in (signal.SIGTERM, signal.SIGINT):
            # Flask reloader の子プロセスも含めて終了する
            try:
                # 現在のプロセスがプロセスグループリーダーの場合、全体を終了
                current_pid = os.getpid()
                pgid = os.getpgid(current_pid)
                if current_pid == pgid:
                    logging.info("Terminating process group %d", pgid)
                    os.killpg(pgid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                # プロセスグループ操作に失敗した場合は通常の終了処理
                pass

            _term()

    signal.signal(signal.SIGTERM, enhanced_sig_handler)
    signal.signal(signal.SIGINT, enhanced_sig_handler)

    # バックグラウンド監視をバックグラウンドで開始
    # use_reloader=True の場合、親プロセスと子プロセスの2つが起動する
    # 親プロセスでは WERKZEUG_RUN_MAIN が未設定、子プロセスでは "true"
    # 監視は子プロセスでのみ開始する
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        monitor = rsudp.monitor.BackgroundMonitor(config)
        monitor.start()
        global _background_monitor
        _background_monitor = monitor

    # Flaskアプリケーションを実行
    try:
        app.run(host="0.0.0.0", port=port, threaded=True, use_reloader=True, debug=debug_mode)  # noqa: S104
    except KeyboardInterrupt:
        logging.info("Received KeyboardInterrupt, shutting down...")
        enhanced_sig_handler(signal.SIGINT, None)


if __name__ == "__main__":
    main()
