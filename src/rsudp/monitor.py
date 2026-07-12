"""
バックグラウンド監視（スクリーンショットスキャン + 地震クローラー）の実装.

cli/webui.py から起動される BackgroundMonitor をまとめる。
"""

from __future__ import annotations

import logging
import pathlib
import sqlite3
import threading
import typing

import my_lib.notify.slack
import my_lib.webapp.event
import PIL.Image

import rsudp.config
import rsudp.types

if typing.TYPE_CHECKING:
    import rsudp.screenshot_manager

# スキャン間隔
_SCREENSHOT_SCAN_INTERVAL = 60  # 1 分間隔でスクリーンショットをスキャン
_QUAKE_CRAWL_INTERVAL = 3600  # 1 時間間隔で地震データを取得
_COMPRESS_INTERVAL = 86400  # 1 日間隔でデータ圧縮（miniSEED zstd / スクリーンショット WebP）


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
    # ファイルが存在しない場合は接続しない。
    # sqlite3.connect() は存在しないパスに空ファイルを作成してしまい、
    # earthquakes テーブルの無い空 DB が viewer 側の JOIN で "no such table" を招くため。
    if not db_path.exists():
        return None
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT MAX(updated_at) FROM earthquakes")
            row = cursor.fetchone()
            return row[0] if row else None
    except sqlite3.Error:
        # テーブル未作成（OperationalError: no such table）等も含めて None を返す。
        logging.exception("Failed to get quake db state")
        return None


class BackgroundMonitor:
    """スクリーンショット監視と地震クローラーをまとめて管理する."""

    def __init__(self, config: rsudp.config.Config) -> None:
        self.config = config
        self._stop_event = threading.Event()
        self._monitor_thread: threading.Thread | None = None
        self._cache_watch_thread: threading.Thread | None = None
        self._cache_watch_stop_event: threading.Event | None = None
        self._quake_watch_thread: threading.Thread | None = None
        self._quake_watch_stop_event: threading.Event | None = None

    def start(self) -> None:
        """全てのバックグラウンドスレッドを起動する."""
        # DB スキーマの初期化・マイグレーションをリクエスト受付前に確定させる。
        # statistics API は cache.db / quake.db を生 SQL で参照するため、
        # 監視スレッドの初回処理任せにすると移行前の形式を読む可能性がある。
        import rsudp.quake.database
        import rsudp.screenshot_manager

        rsudp.screenshot_manager.ScreenshotManager(self.config)
        rsudp.quake.database.QuakeDatabase(self.config)

        self._stop_event.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

        if self._cache_watch_thread is None:
            (
                self._cache_watch_stop_event,
                self._cache_watch_thread,
            ) = my_lib.webapp.event.start_db_state_watcher(
                self.config.data.cache,
                _get_cache_state,
                my_lib.webapp.event.EVENT_TYPE.CONTENT,
            )

        if self._quake_watch_thread is None:
            (
                self._quake_watch_stop_event,
                self._quake_watch_thread,
            ) = my_lib.webapp.event.start_db_state_watcher(
                self.config.data.quake,
                _get_quake_state,
                my_lib.webapp.event.EVENT_TYPE.CONTENT,
            )

    def stop(self) -> None:
        """全てのバックグラウンドスレッドを停止する."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            logging.info("Stopping background monitor...")
            self._stop_event.set()
            self._monitor_thread.join(timeout=5)
            self._monitor_thread = None

        if self._cache_watch_thread is not None and self._cache_watch_stop_event is not None:
            my_lib.webapp.event.stop_db_state_watcher(self._cache_watch_stop_event, self._cache_watch_thread)
            self._cache_watch_thread = None
            self._cache_watch_stop_event = None

        if self._quake_watch_thread is not None and self._quake_watch_stop_event is not None:
            my_lib.webapp.event.stop_db_state_watcher(self._quake_watch_stop_event, self._quake_watch_thread)
            self._quake_watch_thread = None
            self._quake_watch_stop_event = None

    # --- private ---

    def _monitor_loop(self) -> None:
        """定期実行ループ（スクリーンショット + 地震データ）."""
        quake_interval_count = _QUAKE_CRAWL_INTERVAL // _SCREENSHOT_SCAN_INTERVAL
        compress_interval_count = _COMPRESS_INTERVAL // _SCREENSHOT_SCAN_INTERVAL
        loop_count = 0
        compress_loop_count = 0

        logging.info(
            "バックグラウンド監視開始 (スクリーンショット: %d秒間隔, 地震: %d秒間隔)",
            _SCREENSHOT_SCAN_INTERVAL,
            _QUAKE_CRAWL_INTERVAL,
        )

        # 起動時に完全スキャンを 1 回実行
        self._scan_full()
        self._crawl_earthquakes()

        # 定期実行ループ（増分スキャン）
        while not self._stop_event.wait(_SCREENSHOT_SCAN_INTERVAL):
            loop_count += 1
            compress_loop_count += 1

            new_files = self._scan_incremental()

            quake_updated = False
            if loop_count >= quake_interval_count:
                loop_count = 0
                quake_updated = self._crawl_earthquakes()

            if compress_loop_count >= compress_interval_count:
                compress_loop_count = 0
                self._compress_data()

            if new_files > 0 or quake_updated:
                logging.debug("Background monitor detected updates")

        logging.info("バックグラウンド監視停止")

    def _scan_full(self) -> int:
        """完全スキャンを実行し、新規ファイル数を返す."""
        import rsudp.screenshot_manager

        try:
            manager = rsudp.screenshot_manager.ScreenshotManager(self.config)
            manager.organize_files()
            new_count = manager.scan_and_cache_all()
            if new_count > 0:
                logging.info("スクリーンショット監視（完全スキャン）: %d件の新規ファイルを検出", new_count)
            return new_count
        except Exception:
            logging.exception("スクリーンショットスキャンエラー")
            return 0

    def _scan_incremental(self) -> int:
        """増分スキャンを実行し、新規ファイル数を返す."""
        import rsudp.screenshot_manager

        try:
            manager = rsudp.screenshot_manager.ScreenshotManager(self.config)
            manager.organize_files()
            new_count = manager.scan_incremental()
            if new_count > 0:
                logging.info("スクリーンショット監視（増分スキャン）: %d件の新規ファイルを検出", new_count)
                self._notify_detection(manager)
            return new_count
        except Exception:
            logging.exception("スクリーンショットスキャンエラー")
            return 0

    def _crawl_earthquakes(self) -> bool:
        """地震データを取得する. 新規があれば True."""
        import rsudp.quake.crawl

        try:
            logging.info("地震クローラー: 地震データの収集を開始")
            new_earthquakes = rsudp.quake.crawl.crawl_earthquakes(self.config, min_intensity=2)
            self._log_crawl_results(new_earthquakes)
            self._update_earthquake_associations()
            self._notify_matched_earthquakes(new_earthquakes)
            return len(new_earthquakes) > 0
        except Exception:
            logging.exception("地震クローラーエラー")
            return False

    def _compress_data(self) -> None:
        """miniSEED と スクリーンショットを圧縮してディスク使用量を削減する."""
        import rsudp.compress

        try:
            if self.config.data.miniseed is not None:
                result = rsudp.compress.compress_miniseed(self.config.data.miniseed)
                if result.processed > 0:
                    logging.info(
                        "miniSEED 圧縮: %d件, 削減 %.1f MB", result.processed, result.saved / 1024 / 1024
                    )

                # 確定済みの古い miniSEED から地震前後の区間のみを抽出（不可逆）
                # 設定で明示的に有効化されている場合のみ実行する
                if self.config.data.miniseed_extract_quake:
                    result = rsudp.compress.extract_earthquake_miniseed(
                        self.config.data.miniseed, self.config.data.quake
                    )
                    if result.processed > 0 or result.deleted > 0:
                        logging.info(
                            "地震区間抽出: 抽出 %d件, 削除 %d件, 削減 %.1f MB",
                            result.processed,
                            result.deleted,
                            result.saved / 1024 / 1024,
                        )

            result = rsudp.compress.convert_screenshots(
                self.config.plot.screenshot.path, self.config.data.cache
            )
            if result.processed > 0:
                logging.info(
                    "スクリーンショット WebP 変換: %d件, 削減 %.1f MB",
                    result.processed,
                    result.saved / 1024 / 1024,
                )
        except Exception:
            logging.exception("データ圧縮エラー")

    def _update_earthquake_associations(self) -> None:
        """スクリーンショットと地震の関連付けを更新する."""
        import rsudp.screenshot_manager

        try:
            manager = rsudp.screenshot_manager.ScreenshotManager(self.config)
            updated = manager.update_earthquake_associations(self.config.data.quake)
            logging.info("地震関連付け更新完了: %d 件", updated)
        except Exception:
            logging.exception("地震関連付け更新エラー")

    # --- Slack 通知 ---

    def _notify_info(
        self,
        title: str,
        message: str,
        image_path: pathlib.Path | None = None,
    ) -> None:
        """
        info チャンネルへ通知する.

        info チャンネルを持つ設定（SlackErrorInfoConfig）のときのみ実際に送信する。
        SlackEmptyConfig は no-op、SlackErrorOnlyConfig は info 未設定のため通知しない。
        通知失敗が監視処理を巻き込まないよう、広く例外を捕捉する。
        """
        slack = self.config.slack
        if not isinstance(
            slack,
            my_lib.notify.slack.SlackErrorInfoConfig | my_lib.notify.slack.SlackEmptyConfig,
        ):
            return

        try:
            ch_id = (
                slack.info.channel.id if isinstance(slack, my_lib.notify.slack.SlackErrorInfoConfig) else None
            )
            if image_path is not None and ch_id is not None and image_path.exists():
                with PIL.Image.open(image_path) as img:
                    my_lib.notify.slack.upload_image(slack, ch_id, title, img, message)
            else:
                my_lib.notify.slack.info(slack, title, message)
        except Exception:
            # Slack 通知の失敗でスキャン・クロール処理を止めない
            logging.exception("Slack 通知に失敗しました")

    def _screenshot_image_path(self, meta: rsudp.types.ScreenshotMetadata) -> pathlib.Path:
        """スクリーンショットメタデータから画像ファイルの絶対パスを解決する."""
        return self.config.plot.screenshot.path / meta.filepath

    @staticmethod
    def _to_jst_str(timestamp: str) -> str:
        """ISO 形式のタイムスタンプ（UTC）を JST の表示文字列に変換する."""
        return rsudp.types.to_jst(timestamp).strftime("%Y-%m-%d %H:%M:%S JST")

    def _notify_detection(self, manager: rsudp.screenshot_manager.ScreenshotManager) -> None:
        """増分スキャンの新規スクリーンショットのうち代表 1 枚を地震検出候補として通知する."""
        meta = manager.get_representative_new_screenshot()
        if meta is None:
            return

        parts: list[str] = []
        if meta.max_count is not None:
            parts.append(f"MaxCount={meta.max_count:.0f}")
        if meta.sta_lta_ratio is not None:
            parts.append(f"STA/LTA={meta.sta_lta_ratio:.2f}")
        detail = " ".join(parts)
        message = f"地震かも？ {detail} {self._to_jst_str(meta.timestamp)}".strip()

        self._notify_info("地震を検出したかもしれません", message, self._screenshot_image_path(meta))

    def _notify_matched_earthquakes(self, new_earthquakes: list[dict]) -> None:
        """新規地震のうち自局スクリーンショットと照合が取れたものを確定通知する."""
        if not new_earthquakes:
            return
        # info チャンネルが無い設定では照合処理自体をスキップする
        if not isinstance(
            self.config.slack,
            my_lib.notify.slack.SlackErrorInfoConfig | my_lib.notify.slack.SlackEmptyConfig,
        ):
            return

        import rsudp.screenshot_manager

        manager = rsudp.screenshot_manager.ScreenshotManager(self.config)
        for eq in new_earthquakes:
            event_id = eq.get("event_id")
            if not event_id:
                continue

            meta = manager.get_representative_screenshot_for_earthquake(event_id)
            if meta is None:
                # 自局で検出していない遠地地震は通知しない
                continue

            message = (
                f"M{eq['magnitude']:.1f} {eq['epicenter_name']} "
                f"震度{eq['max_intensity']} 深さ{eq['depth']}km\n"
                f"自局でも検出（{self._to_jst_str(meta.timestamp)}）"
            )
            self._notify_info("地震を検出しました", message, self._screenshot_image_path(meta))

    @staticmethod
    def _log_crawl_results(new_earthquakes: list[dict]) -> None:
        """クロール結果をログ出力する."""
        if not new_earthquakes:
            logging.info("地震クローラー: 新規地震なし")
            return

        logging.info("地震クローラー: %d件の新規地震を追加", len(new_earthquakes))
        for eq in new_earthquakes:
            logging.info(
                "  - %s %s M%.1f 震度%s 深さ%dkm",
                rsudp.types.to_jst(eq["detected_at"]).strftime("%Y-%m-%d %H:%M"),
                eq["epicenter_name"],
                eq["magnitude"],
                eq["max_intensity"],
                eq["depth"],
            )
