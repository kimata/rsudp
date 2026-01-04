#!/usr/bin/env python3
"""
rsudp のプロットデータを表示する Web UI サーバです。

Usage:
  webui.py [-c CONFIG] [-p PORT] [-D]

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
import threading

import flask
import flask_cors
import my_lib.config
import my_lib.logger
import my_lib.proc_util

import rsudp.config

SCHEMA_CONFIG = "schema/config.schema"

# 地震データクローラーのデフォルト設定
QUAKE_CRAWL_INTERVAL = 3600  # 1時間間隔

# グローバル変数でクローラースレッドを管理
_quake_crawler_stop_event = threading.Event()
_quake_crawler_thread = None


def start_quake_crawler(config: rsudp.config.Config, interval: int = QUAKE_CRAWL_INTERVAL):
    """地震データクローラーをバックグラウンドで開始する"""
    global _quake_crawler_thread

    def _log_crawl_results(new_earthquakes: list[dict]):
        """クロール結果をログ出力する"""
        if new_earthquakes:
            logging.info("地震クローラー: %d件の新規地震を追加", len(new_earthquakes))
            for eq in new_earthquakes:
                logging.info(
                    "  - %s %s M%.1f 震度%s 深さ%dkm",
                    eq["detected_at"].strftime("%Y-%m-%d %H:%M"),
                    eq["epicenter_name"],
                    eq["magnitude"],
                    eq["max_intensity"],
                    eq["depth"],
                )
        else:
            logging.info("地震クローラー: 新規地震なし")

    def crawler_loop():
        from rsudp.quake.crawl import crawl_earthquakes

        logging.info("地震クローラー開始 (収集間隔: %d秒)", interval)

        # 起動時に即座に1回実行
        try:
            logging.info("地震クローラー: 地震データの収集を開始")
            new_earthquakes = crawl_earthquakes(config, min_intensity=3)
            _log_crawl_results(new_earthquakes)
        except Exception:
            logging.exception("地震クローラーエラー")

        # 定期実行ループ
        while not _quake_crawler_stop_event.wait(interval):
            try:
                logging.info("地震クローラー: 地震データの収集を開始")
                new_earthquakes = crawl_earthquakes(config, min_intensity=3)
                _log_crawl_results(new_earthquakes)
            except Exception:
                logging.exception("地震クローラーエラー")

        logging.info("地震クローラー停止")

    _quake_crawler_stop_event.clear()
    _quake_crawler_thread = threading.Thread(target=crawler_loop, daemon=True)
    _quake_crawler_thread.start()


def stop_quake_crawler():
    """地震データクローラーを停止する"""
    global _quake_crawler_thread

    if _quake_crawler_thread and _quake_crawler_thread.is_alive():
        logging.info("Stopping earthquake crawler...")
        _quake_crawler_stop_event.set()
        _quake_crawler_thread.join(timeout=5)
        _quake_crawler_thread = None


def term():
    # 地震データクローラーを停止
    stop_quake_crawler()

    # 子プロセスを終了
    my_lib.proc_util.kill_child()

    # プロセス終了
    logging.info("Graceful shutdown completed")
    sys.exit(0)


def sig_handler(num, frame):
    logging.warning("receive signal %d", num)

    if num in (signal.SIGTERM, signal.SIGINT):
        term()


def create_app(config: rsudp.config.Config):
    # NOTE: アクセスログは無効にする
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    import my_lib.webapp.config

    my_lib.webapp.config.URL_PREFIX = "/rsudp"
    my_lib.webapp.config.init(
        my_lib.webapp.config.WebappConfig(static_dir_path=config.webapp.static_dir_path)
    )

    import my_lib.webapp.base
    import my_lib.webapp.util

    import rsudp.webui.api.viewer

    app = flask.Flask(__name__)

    flask_cors.CORS(app)

    app.config["CONFIG"] = config

    # OGPルートを優先するため、viewer blueprintを先に登録
    app.register_blueprint(rsudp.webui.api.viewer.blueprint)
    app.register_blueprint(my_lib.webapp.base.blueprint, url_prefix=my_lib.webapp.config.URL_PREFIX)
    app.register_blueprint(my_lib.webapp.base.blueprint_default)
    app.register_blueprint(my_lib.webapp.util.blueprint, url_prefix=my_lib.webapp.config.URL_PREFIX)

    my_lib.webapp.config.show_handler_list(app)

    return app


if __name__ == "__main__":
    import atexit
    import contextlib

    import docopt

    assert __doc__ is not None  # noqa: S101 - type narrowing for pyright
    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    port = args["-p"]
    debug_mode = args["-D"]

    my_lib.logger.init("rsudp", level=logging.DEBUG if debug_mode else logging.INFO)

    config_dict = my_lib.config.load(config_file, pathlib.Path(SCHEMA_CONFIG))
    config = rsudp.config.load_from_dict(config_dict, pathlib.Path.cwd())

    app = create_app(config)

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

            term()

    signal.signal(signal.SIGTERM, enhanced_sig_handler)
    signal.signal(signal.SIGINT, enhanced_sig_handler)

    # 地震データクローラーをバックグラウンドで開始
    # リローダー使用時は子プロセス（WERKZEUG_RUN_MAIN=true）でのみ開始
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not debug_mode:
        start_quake_crawler(config)

    # Flaskアプリケーションを実行
    try:
        # NOTE: キャッシュ機能により初期化が重いため、開発時も自動リロードは無効化
        app.run(host="0.0.0.0", port=port, threaded=True, use_reloader=True, debug=debug_mode)  # noqa: S104
    except KeyboardInterrupt:
        logging.info("Received KeyboardInterrupt, shutting down...")
        enhanced_sig_handler(signal.SIGINT, None)
