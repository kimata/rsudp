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
import sqlite3
import sys
import threading

import flask
import flask_cors
import my_lib.config
import my_lib.logger
import my_lib.proc_util
import my_lib.webapp.event

import rsudp.config

_SCHEMA_CONFIG = "schema/config.schema"

# バックグラウンド監視の設定
_SCREENSHOT_SCAN_INTERVAL = 60  # 1分間隔でスクリーンショットをスキャン
_QUAKE_CRAWL_INTERVAL = 3600  # 1時間間隔で地震データを取得

# グローバル変数で監視スレッドを管理
_monitor_stop_event = threading.Event()
_monitor_thread: threading.Thread | None = None
_cache_watch_thread: threading.Thread | None = None
_cache_watch_stop_event: threading.Event | None = None
_quake_watch_thread: threading.Thread | None = None
_quake_watch_stop_event: threading.Event | None = None


def _get_cache_state(db_path: pathlib.Path) -> str | None:
    """スクリーンショットキャッシュ DB の状態を取得する."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT MAX(timestamp) FROM screenshot_metadata")
            row = cursor.fetchone()
            return row[0] if row else None
    except sqlite3.Error:
        logging.exception("Failed to get cache db state")
        return None


def _get_quake_state(db_path: pathlib.Path) -> str | None:
    """地震 DB の状態を取得する."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT MAX(updated_at) FROM earthquakes")
            row = cursor.fetchone()
            return row[0] if row else None
    except sqlite3.Error:
        logging.exception("Failed to get quake db state")
        return None


def _start_background_monitor(config: rsudp.config.Config):
    """バックグラウンド監視スレッドを開始する（スクリーンショット監視 + 地震クローラー）"""
    global _monitor_thread
    global _cache_watch_thread, _cache_watch_stop_event
    global _quake_watch_thread, _quake_watch_stop_event

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

    def _update_earthquake_associations():
        """スクリーンショットと地震の関連付けを更新する."""
        from rsudp.screenshot_manager import ScreenshotManager

        try:
            manager = ScreenshotManager(config)
            updated = manager.update_earthquake_associations(config.data.quake)
            logging.info("地震関連付け更新完了: %d 件", updated)
        except Exception:
            logging.exception("地震関連付け更新エラー")

    def _crawl_earthquakes():
        """地震データを取得する"""
        from rsudp.quake.crawl import crawl_earthquakes

        try:
            logging.info("地震クローラー: 地震データの収集を開始")
            new_earthquakes = crawl_earthquakes(config, min_intensity=3)
            _log_crawl_results(new_earthquakes)
            _update_earthquake_associations()
            return len(new_earthquakes) > 0
        except Exception:
            logging.exception("地震クローラーエラー")
            return False

    def _scan_screenshots_full() -> int:
        """完全スキャンを実行し、新規ファイル数を返す."""
        from rsudp.screenshot_manager import ScreenshotManager

        try:
            manager = ScreenshotManager(config)
            manager.organize_files()
            new_count = manager.scan_and_cache_all()
            if new_count > 0:
                logging.info("スクリーンショット監視（完全スキャン）: %d件の新規ファイルを検出", new_count)
            return new_count
        except Exception:
            logging.exception("スクリーンショットスキャンエラー")
            return 0

    def _scan_screenshots_incremental() -> int:
        """増分スキャンを実行し、新規ファイル数を返す."""
        from rsudp.screenshot_manager import ScreenshotManager

        try:
            manager = ScreenshotManager(config)
            manager.organize_files()
            new_count = manager.scan_incremental()
            if new_count > 0:
                logging.info("スクリーンショット監視（増分スキャン）: %d件の新規ファイルを検出", new_count)
            return new_count
        except Exception:
            logging.exception("スクリーンショットスキャンエラー")
            return 0

    def monitor_loop():
        quake_interval_count = _QUAKE_CRAWL_INTERVAL // _SCREENSHOT_SCAN_INTERVAL
        loop_count = 0

        logging.info(
            "バックグラウンド監視開始 (スクリーンショット: %d秒間隔, 地震: %d秒間隔)",
            _SCREENSHOT_SCAN_INTERVAL,
            _QUAKE_CRAWL_INTERVAL,
        )

        # 起動時に完全スキャンを1回実行
        _scan_screenshots_full()
        _crawl_earthquakes()

        # 定期実行ループ（増分スキャン）
        while not _monitor_stop_event.wait(_SCREENSHOT_SCAN_INTERVAL):
            loop_count += 1
            new_files = 0
            quake_updated = False

            # スクリーンショット増分スキャン（毎回）
            new_files = _scan_screenshots_incremental()

            # 地震クロール（1時間ごと）
            if loop_count >= quake_interval_count:
                loop_count = 0
                quake_updated = _crawl_earthquakes()

            # 更新があればクライアントに通知
            if new_files > 0 or quake_updated:
                logging.debug("Background monitor detected updates")

        logging.info("バックグラウンド監視停止")

    _monitor_stop_event.clear()
    _monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    _monitor_thread.start()

    if _cache_watch_thread is None:
        _cache_watch_stop_event, _cache_watch_thread = my_lib.webapp.event.start_db_state_watcher(
            config.data.cache,
            _get_cache_state,
            my_lib.webapp.event.EVENT_TYPE.CONTENT,
        )

    if _quake_watch_thread is None:
        _quake_watch_stop_event, _quake_watch_thread = my_lib.webapp.event.start_db_state_watcher(
            config.data.quake,
            _get_quake_state,
            my_lib.webapp.event.EVENT_TYPE.CONTENT,
        )


def _stop_background_monitor():
    """バックグラウンド監視スレッドを停止する"""
    global _monitor_thread
    global _cache_watch_thread, _cache_watch_stop_event
    global _quake_watch_thread, _quake_watch_stop_event

    if _monitor_thread and _monitor_thread.is_alive():
        logging.info("Stopping background monitor...")
        _monitor_stop_event.set()
        _monitor_thread.join(timeout=5)
        _monitor_thread = None

    if _cache_watch_thread is not None and _cache_watch_stop_event is not None:
        my_lib.webapp.event.stop_db_state_watcher(_cache_watch_stop_event, _cache_watch_thread)
        _cache_watch_thread = None
        _cache_watch_stop_event = None

    if _quake_watch_thread is not None and _quake_watch_stop_event is not None:
        my_lib.webapp.event.stop_db_state_watcher(_quake_watch_stop_event, _quake_watch_thread)
        _quake_watch_thread = None
        _quake_watch_stop_event = None


def _term():
    # バックグラウンド監視を停止
    _stop_background_monitor()

    # 子プロセスを終了
    my_lib.proc_util.kill_child()

    # プロセス終了
    logging.info("Graceful shutdown completed")
    sys.exit(0)


def _sig_handler(num, frame):
    logging.warning("receive signal %d", num)

    if num in (signal.SIGTERM, signal.SIGINT):
        _term()


def _create_app(config: rsudp.config.Config):
    # NOTE: アクセスログは無効にする
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    import my_lib.webapp.config

    my_lib.webapp.config.URL_PREFIX = "/rsudp"
    # static_dir_path が相対パスの場合、base_dir（config.yaml の親ディレクトリ）から解決
    static_dir_path = config.webapp.static_dir_path
    if not static_dir_path.is_absolute():
        static_dir_path = (config.base_dir / static_dir_path).resolve()
    my_lib.webapp.config.init(my_lib.webapp.config.WebappConfig(static_dir_path=static_dir_path))

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
    # SSE イベント通知用エンドポイント
    app.register_blueprint(my_lib.webapp.event.blueprint, url_prefix=my_lib.webapp.config.URL_PREFIX)

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
        _start_background_monitor(config)

    # Flaskアプリケーションを実行
    try:
        app.run(host="0.0.0.0", port=port, threaded=True, use_reloader=True, debug=debug_mode)  # noqa: S104
    except KeyboardInterrupt:
        logging.info("Received KeyboardInterrupt, shutting down...")
        enhanced_sig_handler(signal.SIGINT, None)


if __name__ == "__main__":
    main()
