"""
スクリーンショットファイルの管理とメタデータキャッシュ機能を提供する.

タイムゾーンの扱い:
    - スクリーンショットのファイル名に含まれるタイムスタンプ: UTC
    - 地震データ（気象庁API由来）のタイムスタンプ: JST (+09:00)
    - 比較時は datetime オブジェクト同士で比較し、タイムゾーンを正しく考慮する
"""

import logging
import re
import shutil
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from PIL import Image

import rsudp.config
import rsudp.schema_util


class ScreenshotManager:
    """スクリーンショットファイルの管理とメタデータキャッシュを行うクラス."""

    def __init__(self, config: rsudp.config.Config):
        """設定を使用して ScreenshotManager を初期化する."""
        self.config = config
        self.screenshot_path = config.plot.screenshot.path
        self.cache_path = config.data.cache

        # キャッシュディレクトリを作成
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        # データベースを初期化
        self._init_database()

    def _init_database(self):
        """メタデータキャッシュ用の SQLite データベースを初期化する."""
        with sqlite3.connect(self.cache_path) as conn:
            rsudp.schema_util.init_database(conn, "screenshot_metadata")

    def organize_files(self):
        """スクリーンショットファイルを日付ベースのサブディレクトリに整理する."""
        if not self.screenshot_path.exists():
            return

        # ルートディレクトリ内のすべての PNG ファイルを取得
        for file_path in self.screenshot_path.glob("*.png"):
            if not file_path.is_file():
                continue

            # ファイル名から日付を解析
            parsed = self._parse_filename(file_path.name)
            if not parsed:
                continue

            # 日付ベースのサブディレクトリを作成 (YYYY/MM/DD)
            date_dir = (
                self.screenshot_path / str(parsed["year"]) / f"{parsed['month']:02d}" / f"{parsed['day']:02d}"
            )
            date_dir.mkdir(parents=True, exist_ok=True)

            # ファイルをサブディレクトリに移動
            new_path = date_dir / file_path.name
            if not new_path.exists():
                shutil.move(str(file_path), str(new_path))

                # キャッシュを新しいファイル位置で更新
                self._cache_file_metadata(new_path)

    def _parse_filename(self, filename: str) -> dict | None:
        """
        スクリーンショットのファイル名からタイムスタンプ情報を抽出する.

        ファイル名のタイムスタンプは UTC として解釈される.
        """
        pattern = r"^(.+?)-(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})(\d{2})\.png$"
        match = re.match(pattern, filename)

        if not match:
            return None

        prefix, year, month, day, hour, minute, second = match.groups()

        # ファイル名のタイムスタンプは UTC
        timestamp_utc = datetime(
            int(year), int(month), int(day), int(hour), int(minute), int(second), tzinfo=UTC
        )

        return {
            "filename": filename,
            "prefix": prefix,
            "year": int(year),
            "month": int(month),
            "day": int(day),
            "hour": int(hour),
            "minute": int(minute),
            "second": int(second),
            "timestamp": timestamp_utc.isoformat(),
        }

    def _extract_metadata(self, file_path: Path) -> dict:
        """PNG ファイルから STA 値などのメタデータを抽出する."""
        metadata = {}

        try:
            with Image.open(file_path) as img:
                info = img.info

                # PNG メタデータの Description フィールドを確認
                description = info.get("Description", "")

                if description:
                    metadata["raw"] = description

                    # STA, LTA, ratio, MaxCount の値を解析
                    sta_match = re.search(r"STA=([0-9.]+)", description)
                    lta_match = re.search(r"LTA=([0-9.]+)", description)
                    ratio_match = re.search(r"STA/LTA=([0-9.]+)", description)
                    max_count_match = re.search(r"MaxCount=([0-9.]+)", description)

                    if sta_match:
                        metadata["sta"] = float(sta_match.group(1))
                    if lta_match:
                        metadata["lta"] = float(lta_match.group(1))
                    if ratio_match:
                        metadata["sta_lta_ratio"] = float(ratio_match.group(1))
                    if max_count_match:
                        metadata["max_count"] = float(max_count_match.group(1))

                # Description がない場合は Comment フィールドも確認
                if not description and "Comment" in info:
                    comment = info.get("Comment", "")
                    if comment and "raw" not in metadata:
                        metadata["comment"] = comment

        except Exception:
            logging.exception("メタデータの抽出に失敗: %s", file_path)

        return metadata

    def _cache_file_metadata(self, file_path: Path):
        """ファイルのメタデータを SQLite データベースにキャッシュする."""
        if not file_path.exists():
            return

        parsed = self._parse_filename(file_path.name)
        if not parsed:
            return

        metadata = self._extract_metadata(file_path)
        stat = file_path.stat()

        with sqlite3.connect(self.cache_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO screenshot_metadata
                (filename, filepath, year, month, day, hour, minute, second,
                 timestamp, sta_value, lta_value, sta_lta_ratio, max_count,
                 created_at, file_size, metadata_raw)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    file_path.name,
                    str(file_path.relative_to(self.screenshot_path)),
                    parsed["year"],
                    parsed["month"],
                    parsed["day"],
                    parsed["hour"],
                    parsed["minute"],
                    parsed["second"],
                    parsed["timestamp"],
                    metadata.get("sta"),
                    metadata.get("lta"),
                    metadata.get("sta_lta_ratio"),
                    metadata.get("max_count"),
                    stat.st_ctime,
                    stat.st_size,
                    metadata.get("raw"),
                ),
            )

    def scan_and_cache_all(self):
        """すべてのスクリーンショットファイルをスキャンしてキャッシュを更新する."""
        if not self.screenshot_path.exists():
            return

        # すべての PNG ファイルを再帰的に取得
        for file_path in self.screenshot_path.rglob("*.png"):
            if not file_path.is_file():
                continue

            # すでにキャッシュされているか確認
            with sqlite3.connect(self.cache_path) as conn:
                cursor = conn.execute(
                    "SELECT file_size FROM screenshot_metadata WHERE filename = ?", (file_path.name,)
                )
                row = cursor.fetchone()

                # キャッシュ済みでファイルサイズが変わっていなければスキップ
                if row and row[0] == file_path.stat().st_size:
                    continue

            self._cache_file_metadata(file_path)

    def get_screenshots_with_signal_filter(self, min_max_signal: float | None = None):
        """最小信号値（max_count）でフィルタリングしたスクリーンショットを取得する."""
        with sqlite3.connect(self.cache_path) as conn:
            query = """
                SELECT filename, filepath, year, month, day, hour, minute, second,
                       timestamp, sta_value, lta_value, sta_lta_ratio, max_count, metadata_raw
                FROM screenshot_metadata
            """
            params = []

            if min_max_signal is not None:
                query += " WHERE max_count >= ?"
                params.append(min_max_signal)

            query += " ORDER BY timestamp DESC"

            cursor = conn.execute(query, params)

            return [
                {
                    "filename": row[0],
                    "filepath": row[1],
                    "year": row[2],
                    "month": row[3],
                    "day": row[4],
                    "hour": row[5],
                    "minute": row[6],
                    "second": row[7],
                    "timestamp": row[8],
                    "sta": row[9],
                    "lta": row[10],
                    "sta_lta_ratio": row[11],
                    "max_count": row[12],
                    "metadata": row[13],
                }
                for row in cursor
            ]

    def get_available_dates(self, min_max_signal: float | None = None):
        """最小信号値を満たすスクリーンショットが存在する日付のリストを取得する."""
        with sqlite3.connect(self.cache_path) as conn:
            query = """
                SELECT DISTINCT year, month, day
                FROM screenshot_metadata
            """
            params = []

            if min_max_signal is not None:
                query += " WHERE max_count >= ?"
                params.append(min_max_signal)

            query += " ORDER BY year DESC, month DESC, day DESC"

            cursor = conn.execute(query, params)

            return [{"year": row[0], "month": row[1], "day": row[2]} for row in cursor]

    def get_signal_statistics(
        self,
        quake_db_path: Path | None = None,
        *,
        earthquake_only: bool = False,
        before_seconds: int = 30,
        after_seconds: int = 240,
    ):
        """
        信号値（max_count）の統計情報を取得する.

        Args:
            quake_db_path: 地震データベースのパス
            earthquake_only: Trueの場合、地震時間帯のスクリーンショットのみ対象
            before_seconds: 地震発生前の許容秒数
            after_seconds: 地震発生後の許容秒数

        """
        if earthquake_only and quake_db_path and quake_db_path.exists():
            # 地震フィルタ時は該当するスクリーンショットのみで統計を計算
            screenshots = self.get_screenshots_with_earthquake_filter(
                quake_db_path=quake_db_path,
                before_seconds=before_seconds,
                after_seconds=after_seconds,
            )

            if not screenshots:
                return {
                    "total": 0,
                    "min_signal": None,
                    "max_signal": None,
                    "avg_signal": None,
                    "with_signal": 0,
                }

            max_counts = [s["max_count"] for s in screenshots if s["max_count"] is not None]
            return {
                "total": len(screenshots),
                "min_signal": min(max_counts) if max_counts else None,
                "max_signal": max(max_counts) if max_counts else None,
                "avg_signal": sum(max_counts) / len(max_counts) if max_counts else None,
                "with_signal": len(max_counts),
            }

        # 通常の統計
        with sqlite3.connect(self.cache_path) as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    MIN(max_count) as min_signal,
                    MAX(max_count) as max_signal,
                    AVG(max_count) as avg_signal,
                    COUNT(CASE WHEN max_count IS NOT NULL THEN 1 END) as with_signal
                FROM screenshot_metadata
            """)

            row = cursor.fetchone()
            return {
                "total": row[0],
                "min_signal": row[1],
                "max_signal": row[2],
                "avg_signal": row[3],
                "with_signal": row[4],
            }

    def get_screenshots_with_earthquake_filter(
        self,
        min_max_signal: float | None = None,
        quake_db_path: Path | None = None,
        before_seconds: int = 30,
        after_seconds: int = 240,
    ) -> list[dict]:
        """
        地震発生時刻の前後に記録されたスクリーンショットを取得する.

        Args:
            min_max_signal: 最小 max_count フィルタ（オプション）
            quake_db_path: 地震データベースのパス
            before_seconds: 地震発生前の許容秒数
            after_seconds: 地震発生後の許容秒数

        Returns:
            地震情報が付加されたスクリーンショットのリスト

        """
        if not quake_db_path or not quake_db_path.exists():
            return []

        # 地震データを取得（タイムスタンプは JST）
        with sqlite3.connect(quake_db_path) as quake_conn:
            quake_conn.row_factory = sqlite3.Row
            quake_cursor = quake_conn.execute("SELECT * FROM earthquakes ORDER BY detected_at DESC")
            earthquakes = [dict(row) for row in quake_cursor.fetchall()]

        if not earthquakes:
            return []

        # 地震ごとの時間範囲を作成（datetime オブジェクトとして保持）
        # detected_at は JST のタイムゾーン情報を含む ISO 形式文字列
        time_conditions = []
        for eq in earthquakes:
            detected_at = datetime.fromisoformat(eq["detected_at"])
            start_time = detected_at - timedelta(seconds=before_seconds)
            end_time = detected_at + timedelta(seconds=after_seconds)
            time_conditions.append((start_time, end_time, eq))

        # スクリーンショットを取得
        with sqlite3.connect(self.cache_path) as conn:
            query = """
                SELECT filename, filepath, year, month, day, hour, minute, second,
                       timestamp, sta_value, lta_value, sta_lta_ratio, max_count, metadata_raw
                FROM screenshot_metadata
            """
            params = []

            if min_max_signal is not None:
                query += " WHERE max_count >= ?"
                params.append(min_max_signal)

            query += " ORDER BY timestamp DESC"

            cursor = conn.execute(query, params)

            screenshots = []
            for row in cursor:
                # スクリーンショットのタイムスタンプ（UTC、タイムゾーン情報付き）を解析
                screenshot_ts_str = row[8]
                screenshot_ts = datetime.fromisoformat(screenshot_ts_str)

                # 地震の時間範囲と照合
                # 両方ともタイムゾーン情報を持つ datetime なので正しく比較される
                matched_earthquake = None
                for start_time, end_time, eq in time_conditions:
                    if start_time <= screenshot_ts <= end_time:
                        matched_earthquake = eq
                        break

                if matched_earthquake:
                    screenshots.append(
                        {
                            "filename": row[0],
                            "filepath": row[1],
                            "year": row[2],
                            "month": row[3],
                            "day": row[4],
                            "hour": row[5],
                            "minute": row[6],
                            "second": row[7],
                            "timestamp": row[8],
                            "sta": row[9],
                            "lta": row[10],
                            "sta_lta_ratio": row[11],
                            "max_count": row[12],
                            "metadata": row[13],
                            "earthquake": matched_earthquake,
                        }
                    )

            return screenshots

    def get_earthquake_for_screenshot(
        self,
        screenshot_timestamp: str,
        quake_db_path: Path | None = None,
        before_seconds: int = 30,
        after_seconds: int = 240,
    ) -> dict | None:
        """
        指定されたスクリーンショットのタイムスタンプに対応する地震情報を取得する.

        Args:
            screenshot_timestamp: ISO 形式のタイムスタンプ（UTC）
            quake_db_path: 地震データベースのパス
            before_seconds: 地震発生前の許容秒数
            after_seconds: 地震発生後の許容秒数

        Returns:
            地震情報の辞書、または None

        """
        if not quake_db_path or not quake_db_path.exists():
            return None

        # スクリーンショットのタイムスタンプを datetime オブジェクトに変換
        screenshot_dt = datetime.fromisoformat(screenshot_timestamp)

        # 地震データを取得
        with sqlite3.connect(quake_db_path) as quake_conn:
            quake_conn.row_factory = sqlite3.Row
            cursor = quake_conn.execute("SELECT * FROM earthquakes")
            earthquakes = [dict(row) for row in cursor.fetchall()]

        # Python で時間範囲の比較を行う（タイムゾーン情報付き datetime で正しく比較）
        best_match = None
        best_diff = None

        for eq in earthquakes:
            detected_at = datetime.fromisoformat(eq["detected_at"])
            start_time = detected_at - timedelta(seconds=before_seconds)
            end_time = detected_at + timedelta(seconds=after_seconds)

            if start_time <= screenshot_dt <= end_time:
                # 時間差の絶対値を計算
                diff = abs((screenshot_dt - detected_at).total_seconds())
                if best_diff is None or diff < best_diff:
                    best_diff = diff
                    best_match = eq

        return best_match

    def update_earthquake_associations(
        self,
        quake_db_path: Path,
        before_seconds: int = 30,
        after_seconds: int = 240,
    ) -> int:
        """
        全スクリーンショットの地震関連付けを更新する.

        地震データベースを参照し、各スクリーンショットがどの地震に関連するか
        事前計算してキャッシュに保存する。

        Args:
            quake_db_path: 地震データベースのパス
            before_seconds: 地震発生前の許容秒数
            after_seconds: 地震発生後の許容秒数

        Returns:
            更新されたスクリーンショット数

        """
        if not quake_db_path.exists():
            return 0

        # 地震データを取得
        with sqlite3.connect(quake_db_path) as quake_conn:
            quake_conn.row_factory = sqlite3.Row
            quake_cursor = quake_conn.execute("SELECT event_id, detected_at FROM earthquakes")
            earthquakes = [
                (row["event_id"], datetime.fromisoformat(row["detected_at"])) for row in quake_cursor
            ]

        if not earthquakes:
            return 0

        # 地震ごとの時間範囲を作成
        time_ranges = [
            (
                event_id,
                detected_at - timedelta(seconds=before_seconds),
                detected_at + timedelta(seconds=after_seconds),
            )
            for event_id, detected_at in earthquakes
        ]

        updated_count = 0
        with sqlite3.connect(self.cache_path) as conn:
            # 全スクリーンショットのタイムスタンプを取得
            cursor = conn.execute("SELECT filename, timestamp FROM screenshot_metadata")
            rows = cursor.fetchall()

            for filename, timestamp_str in rows:
                screenshot_ts = datetime.fromisoformat(timestamp_str)

                # マッチする地震を探す
                matched_event_id = None
                for event_id, start_time, end_time in time_ranges:
                    if start_time <= screenshot_ts <= end_time:
                        matched_event_id = event_id
                        break

                # 関連付けを更新
                conn.execute(
                    "UPDATE screenshot_metadata SET earthquake_event_id = ? WHERE filename = ?",
                    (matched_event_id, filename),
                )
                if matched_event_id:
                    updated_count += 1

            conn.commit()

        logging.info("地震関連付けを更新: %d 件のスクリーンショットが地震に関連付けられました", updated_count)
        return updated_count

    def get_screenshots_with_earthquake_filter_fast(
        self,
        quake_db_path: Path,
        min_max_signal: float | None = None,
    ) -> list[dict]:
        """
        事前計算された地震関連付けを使って高速にフィルタリングする.

        Args:
            quake_db_path: 地震データベースのパス（地震情報の取得に使用）
            min_max_signal: 最小 max_count フィルタ（オプション）

        Returns:
            地震情報が付加されたスクリーンショットのリスト

        """
        # 地震データを辞書形式で取得
        earthquake_map: dict[str, dict] = {}
        if quake_db_path.exists():
            with sqlite3.connect(quake_db_path) as quake_conn:
                quake_conn.row_factory = sqlite3.Row
                quake_cursor = quake_conn.execute("SELECT * FROM earthquakes")
                for row in quake_cursor:
                    earthquake_map[row["event_id"]] = dict(row)

        # キャッシュから地震関連スクリーンショットを取得
        with sqlite3.connect(self.cache_path) as conn:
            query = """
                SELECT filename, filepath, year, month, day, hour, minute, second,
                       timestamp, sta_value, lta_value, sta_lta_ratio, max_count,
                       metadata_raw, earthquake_event_id
                FROM screenshot_metadata
                WHERE earthquake_event_id IS NOT NULL
            """
            params: list = []

            if min_max_signal is not None:
                query += " AND max_count >= ?"
                params.append(min_max_signal)

            query += " ORDER BY timestamp DESC"

            cursor = conn.execute(query, params)

            screenshots = []
            for row in cursor:
                event_id = row[14]
                earthquake = earthquake_map.get(event_id)

                screenshots.append(
                    {
                        "filename": row[0],
                        "filepath": row[1],
                        "year": row[2],
                        "month": row[3],
                        "day": row[4],
                        "hour": row[5],
                        "minute": row[6],
                        "second": row[7],
                        "timestamp": row[8],
                        "sta": row[9],
                        "lta": row[10],
                        "sta_lta_ratio": row[11],
                        "max_count": row[12],
                        "metadata": row[13],
                        "earthquake": earthquake,
                    }
                )

            return screenshots
