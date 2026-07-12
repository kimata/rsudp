"""
スクリーンショットファイルの管理とメタデータキャッシュ機能を提供する.

タイムゾーンの扱い:
    - スクリーンショットのファイル名に含まれるタイムスタンプ: UTC
    - 地震データ（気象庁API由来）のタイムスタンプ: JST (+09:00)
    - 比較時は datetime オブジェクト同士で比較し、タイムゾーンを正しく考慮する
"""

import datetime
import logging
import re
import shutil
import sqlite3
import typing
from pathlib import Path

import PIL.Image

import rsudp.config
import rsudp.schema_util
import rsudp.types

_T = typing.TypeVar("_T")

# 地震マッチング候補: (時間窓開始, 時間窓終了, 発生時刻, ペイロード)
EarthquakeCandidate = tuple[datetime.datetime, datetime.datetime, datetime.datetime, _T]


def _build_earthquake_candidates(
    earthquakes: list[tuple[str, _T]],
    before_seconds: int,
    after_seconds: int,
) -> list[EarthquakeCandidate[_T]]:
    """
    地震ごとのマッチング候補（時間窓と発生時刻）を構築する.

    Args:
        earthquakes: (detected_at 文字列, ペイロード) のリスト
        before_seconds: 地震発生前の許容秒数
        after_seconds: 地震発生後の許容秒数

    Returns:
        (開始時刻, 終了時刻, 発生時刻 datetime, ペイロード) のリスト

    """
    candidates: list[EarthquakeCandidate[_T]] = []
    for detected_at_str, payload in earthquakes:
        start_time, end_time = rsudp.types.calculate_earthquake_time_range(
            detected_at_str, before_seconds, after_seconds
        )
        detected_at = datetime.datetime.fromisoformat(detected_at_str)
        candidates.append((start_time, end_time, detected_at, payload))
    return candidates


def _find_closest_earthquake(
    screenshot_ts: datetime.datetime,
    candidates: list[EarthquakeCandidate[_T]],
) -> _T | None:
    """
    時間窓内で detected_at がスクリーンショット時刻に最も近い地震のペイロードを返す.

    余震などで複数の時間窓（-30〜+240秒）が重なる場合でも、常に発生時刻が
    最も近い地震を一意に選ぶことで、関連付けの 3 経路で結果を統一する。

    Args:
        screenshot_ts: スクリーンショットのタイムスタンプ（タイムゾーン情報付き）
        candidates: _build_earthquake_candidates() で構築したマッチング候補

    Returns:
        最も近い地震のペイロード、または該当なしの場合は None

    """
    best: _T | None = None
    best_diff: float | None = None
    for start_time, end_time, detected_at, payload in candidates:
        if not (start_time <= screenshot_ts <= end_time):
            continue
        diff = abs((screenshot_ts - detected_at).total_seconds())
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best = payload
    return best


class ScreenshotManager:
    """スクリーンショットファイルの管理とメタデータキャッシュを行うクラス."""

    def __init__(self, config: rsudp.config.Config):
        """設定を使用して ScreenshotManager を初期化する."""
        self.config = config
        self.screenshot_path = config.plot.screenshot.path
        self.cache_path = config.data.cache

        # 直近のスキャンで新規追加されたファイル名（地震検出通知の代表選出に使用）
        self._last_scanned_files: list[str] = []

        # キャッシュディレクトリを作成
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        # データベースを初期化
        self._init_database()

    def _init_database(self):
        """メタデータキャッシュ用の SQLite データベースを初期化する."""
        with sqlite3.connect(self.cache_path) as conn:
            rsudp.schema_util.init_database(conn, "screenshot_metadata")

    @staticmethod
    def _iter_images(directory: Path, *, recursive: bool = False):
        """PNG/WebP のスクリーンショットファイルを列挙する."""
        glob_fn = directory.rglob if recursive else directory.glob
        yield from glob_fn("*.png")
        yield from glob_fn("*.webp")

    def organize_files(self):
        """スクリーンショットファイルを日付ベースのサブディレクトリに整理する."""
        if not self.screenshot_path.exists():
            return

        # ルートディレクトリ内のすべての画像ファイルを取得
        for file_path in self._iter_images(self.screenshot_path):
            if not file_path.is_file():
                continue

            # ファイル名から日付を解析
            parsed = rsudp.types.parse_filename(file_path.name)
            if not parsed:
                continue

            # 日付ベースのサブディレクトリを作成 (YYYY/MM/DD)
            date_dir = self.screenshot_path / str(parsed.year) / f"{parsed.month:02d}" / f"{parsed.day:02d}"
            date_dir.mkdir(parents=True, exist_ok=True)

            # ファイルをサブディレクトリに移動
            new_path = date_dir / file_path.name
            if not new_path.exists():
                shutil.move(file_path, new_path)

                # キャッシュを新しいファイル位置で更新
                self._cache_file_metadata(new_path)

    def _extract_metadata(self, file_path: Path) -> dict:
        """PNG ファイルから STA 値などのメタデータを抽出する."""
        metadata = {}

        try:
            with PIL.Image.open(file_path) as img:
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

        parsed = rsudp.types.parse_filename(file_path.name)
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
                    parsed.year,
                    parsed.month,
                    parsed.day,
                    parsed.hour,
                    parsed.minute,
                    parsed.second,
                    parsed.timestamp,
                    metadata.get("sta"),
                    metadata.get("lta"),
                    metadata.get("sta_lta_ratio"),
                    metadata.get("max_count"),
                    stat.st_ctime,
                    stat.st_size,
                    metadata.get("raw"),
                ),
            )

    def get_latest_cached_date(self) -> rsudp.types.DateInfo | None:
        """
        キャッシュ内の最新のスクリーンショットの日付を取得する.

        Returns:
            最新の日付情報、またはキャッシュが空の場合は None

        """
        with sqlite3.connect(self.cache_path) as conn:
            cursor = conn.execute("""
                SELECT year, month, day
                FROM screenshot_metadata
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                return rsudp.types.DateInfo(year=row[0], month=row[1], day=row[2])
            return None

    def scan_and_cache_all(self) -> int:
        """
        すべてのスクリーンショットファイルをスキャンしてキャッシュを更新する.

        Returns:
            新規または更新されたファイル数

        """
        if not self.screenshot_path.exists():
            return 0

        self._last_scanned_files = []
        new_count = 0

        # すべての画像ファイルを再帰的に取得
        for file_path in self._iter_images(self.screenshot_path, recursive=True):
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
            self._last_scanned_files.append(file_path.name)
            new_count += 1

        return new_count

    def scan_incremental(self) -> int:
        """
        最新のキャッシュ日付以降のファイルのみをスキャンしてキャッシュを更新する.

        増分スキャンは、最新のキャッシュ日付と同じ日付以降のディレクトリのみを
        スキャンすることで、パフォーマンスを向上させる。

        Returns:
            新規または更新されたファイル数

        """
        if not self.screenshot_path.exists():
            return 0

        latest_date = self.get_latest_cached_date()

        # キャッシュが空の場合は完全スキャンにフォールバック
        # （_last_scanned_files は scan_and_cache_all 側で更新される）
        if not latest_date:
            logging.info("増分スキャン: キャッシュが空のため完全スキャンを実行")
            return self.scan_and_cache_all()

        self._last_scanned_files = []
        new_count = 0

        # 最新日付以降のディレクトリをスキャン
        # ディレクトリ構造: YYYY/MM/DD
        for year_dir in self.screenshot_path.iterdir():
            if not year_dir.is_dir() or not year_dir.name.isdigit():
                continue

            year = int(year_dir.name)
            if year < latest_date.year:
                continue

            for month_dir in year_dir.iterdir():
                if not month_dir.is_dir() or not month_dir.name.isdigit():
                    continue

                month = int(month_dir.name)
                if year == latest_date.year and month < latest_date.month:
                    continue

                for day_dir in month_dir.iterdir():
                    if not day_dir.is_dir() or not day_dir.name.isdigit():
                        continue

                    day = int(day_dir.name)
                    if year == latest_date.year and month == latest_date.month and day < latest_date.day:
                        continue

                    # この日付のディレクトリ内のファイルをスキャン
                    for file_path in self._iter_images(day_dir):
                        if not file_path.is_file():
                            continue

                        # すでにキャッシュされているか確認
                        with sqlite3.connect(self.cache_path) as conn:
                            cursor = conn.execute(
                                "SELECT file_size FROM screenshot_metadata WHERE filename = ?",
                                (file_path.name,),
                            )
                            row = cursor.fetchone()

                            # キャッシュ済みでファイルサイズが変わっていなければスキップ
                            if row and row[0] == file_path.stat().st_size:
                                continue

                        self._cache_file_metadata(file_path)
                        self._last_scanned_files.append(file_path.name)
                        new_count += 1

        if new_count > 0:
            logging.info("増分スキャン: %d件の新規ファイルを検出", new_count)

        return new_count

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

            return [rsudp.types.row_to_screenshot_dict(row) for row in cursor]

    def get_available_years(self, min_max_signal: float | None = None) -> list[int]:
        """最小信号値を満たすスクリーンショットが存在する年のリストを取得する."""
        query = "SELECT DISTINCT year FROM screenshot_metadata"
        params: list = []
        if min_max_signal is not None:
            query += " WHERE max_count >= ?"
            params.append(min_max_signal)
        query += " ORDER BY year DESC"

        with sqlite3.connect(self.cache_path) as conn:
            return [row[0] for row in conn.execute(query, params)]

    def get_available_months(self, year: int, min_max_signal: float | None = None) -> list[int]:
        """指定年で利用可能な月のリストを取得する."""
        query = "SELECT DISTINCT month FROM screenshot_metadata WHERE year = ?"
        params: list = [year]
        if min_max_signal is not None:
            query += " AND max_count >= ?"
            params.append(min_max_signal)
        query += " ORDER BY month DESC"

        with sqlite3.connect(self.cache_path) as conn:
            return [row[0] for row in conn.execute(query, params)]

    def get_available_days(self, year: int, month: int, min_max_signal: float | None = None) -> list[int]:
        """指定年月で利用可能な日のリストを取得する."""
        query = "SELECT DISTINCT day FROM screenshot_metadata WHERE year = ? AND month = ?"
        params: list = [year, month]
        if min_max_signal is not None:
            query += " AND max_count >= ?"
            params.append(min_max_signal)
        query += " ORDER BY day DESC"

        with sqlite3.connect(self.cache_path) as conn:
            return [row[0] for row in conn.execute(query, params)]

    @staticmethod
    def _attach_quake_db(conn: sqlite3.Connection, quake_db_path: Path) -> None:
        """quake.db を `quake` スキーマとして接続に attach する."""
        conn.execute("ATTACH DATABASE ? AS quake", (str(quake_db_path),))

    def get_signal_statistics(
        self,
        *,
        earthquake_only: bool = False,
        quake_db_path: Path | None = None,
        min_magnitude: float | None = None,
    ) -> rsudp.types.SignalStatistics:
        """
        信号値（max_count）の統計情報を取得する.

        Args:
            earthquake_only: Trueの場合、地震関連のスクリーンショットのみ対象
                             （事前計算された earthquake_event_id を使用）
            quake_db_path: 地震データベースのパス（min_magnitude 指定時に必要）
            min_magnitude: 最小マグニチュードフィルタ（earthquake_only=True 時のみ有効）

        """
        query = """
            SELECT
                COUNT(*) as total,
                MIN(s.max_count) as min_signal,
                MAX(s.max_count) as max_signal,
                AVG(s.max_count) as avg_signal,
                COUNT(CASE WHEN s.max_count IS NOT NULL THEN 1 END) as with_signal
            FROM screenshot_metadata s
        """
        params: list = []
        needs_quake_attach = False

        if earthquake_only:
            if min_magnitude is not None:
                if quake_db_path is None or not quake_db_path.exists():
                    return rsudp.types.SignalStatistics(total=0)
                query += (
                    " JOIN quake.earthquakes q ON s.earthquake_event_id = q.event_id WHERE q.magnitude >= ?"
                )
                params.append(min_magnitude)
                needs_quake_attach = True
            else:
                query += " WHERE s.earthquake_event_id IS NOT NULL"

        with sqlite3.connect(self.cache_path) as conn:
            if needs_quake_attach:
                assert quake_db_path is not None  # noqa: S101 - type narrowing
                self._attach_quake_db(conn, quake_db_path)
            row = conn.execute(query, params).fetchone()
            return rsudp.types.SignalStatistics(
                total=row[0],
                min_signal=row[1],
                max_signal=row[2],
                avg_signal=row[3],
                with_signal=row[4],
            )

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
            earthquakes = [rsudp.types.EarthquakeData(**dict(row)) for row in quake_cursor.fetchall()]

        if not earthquakes:
            return []

        # 地震ごとのマッチング候補を作成（時間窓が最も近い地震を一意に選ぶため）
        # detected_at は JST のタイムゾーン情報を含む ISO 形式文字列
        candidates = _build_earthquake_candidates(
            [(eq.detected_at, eq) for eq in earthquakes], before_seconds, after_seconds
        )

        # スクリーンショットを取得
        with sqlite3.connect(self.cache_path) as conn:
            query = """
                SELECT filename, filepath, year, month, day, hour, minute, second,
                       timestamp, sta_value, lta_value, sta_lta_ratio, max_count, metadata_raw
                FROM screenshot_metadata
            """
            params: list = []

            if min_max_signal is not None:
                query += " WHERE max_count >= ?"
                params.append(min_max_signal)

            query += " ORDER BY timestamp DESC"

            cursor = conn.execute(query, params)

            screenshots = []
            for row in cursor:
                # スクリーンショットのタイムスタンプ（UTC、タイムゾーン情報付き）を解析
                screenshot_ts = datetime.datetime.fromisoformat(row[8])

                # 時間窓内で発生時刻が最も近い地震を選ぶ（3 経路で統一）
                matched_earthquake = _find_closest_earthquake(screenshot_ts, candidates)

                if matched_earthquake:
                    screenshots.append(rsudp.types.row_to_screenshot_dict(row, matched_earthquake))

            return screenshots

    def get_earthquake_for_screenshot(
        self,
        screenshot_timestamp: str,
        quake_db_path: Path | None = None,
        before_seconds: int = 30,
        after_seconds: int = 240,
    ) -> rsudp.types.EarthquakeData | None:
        """
        指定されたスクリーンショットのタイムスタンプに対応する地震情報を取得する.

        Args:
            screenshot_timestamp: ISO 形式のタイムスタンプ（UTC）
            quake_db_path: 地震データベースのパス
            before_seconds: 地震発生前の許容秒数
            after_seconds: 地震発生後の許容秒数

        Returns:
            EarthquakeData、または None

        """
        if not quake_db_path or not quake_db_path.exists():
            return None

        # スクリーンショットのタイムスタンプを datetime オブジェクトに変換
        screenshot_dt = datetime.datetime.fromisoformat(screenshot_timestamp)

        # 地震データを取得
        with sqlite3.connect(quake_db_path) as quake_conn:
            quake_conn.row_factory = sqlite3.Row
            cursor = quake_conn.execute("SELECT * FROM earthquakes")
            earthquakes = [rsudp.types.EarthquakeData(**dict(row)) for row in cursor.fetchall()]

        # 時間窓内で発生時刻が最も近い地震を選ぶ（3 経路で統一）
        candidates = _build_earthquake_candidates(
            [(eq.detected_at, eq) for eq in earthquakes], before_seconds, after_seconds
        )
        return _find_closest_earthquake(screenshot_dt, candidates)

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

        # 地震データを取得（detected_at は文字列のまま保持）
        with sqlite3.connect(quake_db_path) as quake_conn:
            quake_conn.row_factory = sqlite3.Row
            quake_cursor = quake_conn.execute("SELECT event_id, detected_at FROM earthquakes")
            earthquakes = [(row["event_id"], row["detected_at"]) for row in quake_cursor]

        if not earthquakes:
            return 0

        # 地震ごとのマッチング候補を作成（ペイロードは event_id）
        # 他の 2 経路と同じく「時間窓内で発生時刻が最も近い地震」を選ぶ
        candidates = _build_earthquake_candidates(
            [(detected_at_str, event_id) for event_id, detected_at_str in earthquakes],
            before_seconds,
            after_seconds,
        )

        updated_count = 0
        with sqlite3.connect(self.cache_path) as conn:
            # 全スクリーンショットのタイムスタンプを取得
            cursor = conn.execute("SELECT filename, timestamp FROM screenshot_metadata")
            rows = cursor.fetchall()

            for filename, timestamp_str in rows:
                screenshot_ts = datetime.datetime.fromisoformat(timestamp_str)

                # 時間窓内で発生時刻が最も近い地震を選ぶ
                matched_event_id = _find_closest_earthquake(screenshot_ts, candidates)

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
        min_magnitude: float | None = None,
    ) -> list[dict]:
        """
        事前計算された地震関連付けを使って高速にフィルタリングする.

        Args:
            quake_db_path: 地震データベースのパス（地震情報の取得に使用）
            min_max_signal: 最小 max_count フィルタ（オプション）
            min_magnitude: 最小マグニチュードフィルタ（オプション）

        Returns:
            地震情報が付加されたスクリーンショットのリスト

        """
        if not quake_db_path.exists():
            return []

        query = """
            SELECT s.filename, s.filepath, s.year, s.month, s.day, s.hour, s.minute, s.second,
                   s.timestamp, s.sta_value, s.lta_value, s.sta_lta_ratio, s.max_count, s.metadata_raw,
                   q.id, q.event_id, q.detected_at, q.latitude, q.longitude, q.magnitude,
                   q.depth, q.epicenter_name, q.max_intensity, q.created_at, q.updated_at
            FROM screenshot_metadata s
            JOIN quake.earthquakes q ON s.earthquake_event_id = q.event_id
        """
        conditions: list[str] = []
        params: list = []
        if min_max_signal is not None:
            conditions.append("s.max_count >= ?")
            params.append(min_max_signal)
        if min_magnitude is not None:
            conditions.append("q.magnitude >= ?")
            params.append(min_magnitude)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY s.timestamp DESC"

        with sqlite3.connect(self.cache_path) as conn:
            self._attach_quake_db(conn, quake_db_path)
            cursor = conn.execute(query, params)

            screenshots = []
            for row in cursor:
                earthquake = rsudp.types.EarthquakeData(
                    id=row[14],
                    event_id=row[15],
                    detected_at=row[16],
                    latitude=row[17],
                    longitude=row[18],
                    magnitude=row[19],
                    depth=row[20],
                    epicenter_name=row[21],
                    max_intensity=row[22],
                    created_at=row[23],
                    updated_at=row[24],
                )
                screenshots.append(rsudp.types.row_to_screenshot_dict(row[:14], earthquake))

            return screenshots

    @staticmethod
    def _row_to_metadata(row: tuple) -> rsudp.types.ScreenshotMetadata:
        """14 要素の行タプルを ScreenshotMetadata に変換する."""
        return rsudp.types.ScreenshotMetadata(
            filename=row[0],
            filepath=row[1],
            year=row[2],
            month=row[3],
            day=row[4],
            hour=row[5],
            minute=row[6],
            second=row[7],
            timestamp=row[8],
            sta=row[9],
            lta=row[10],
            sta_lta_ratio=row[11],
            max_count=row[12],
            metadata=row[13],
        )

    _METADATA_COLUMNS = (
        "filename, filepath, year, month, day, hour, minute, second, "
        "timestamp, sta_value, lta_value, sta_lta_ratio, max_count, metadata_raw"
    )

    def get_representative_new_screenshot(self) -> rsudp.types.ScreenshotMetadata | None:
        """
        直近のスキャンで追加されたファイルのうち max_count が最大の 1 枚を返す.

        地震検出通知の代表スクリーンショットとして使用する。
        直近のスキャンで新規追加が無かった場合は None を返す。
        """
        if not self._last_scanned_files:
            return None

        placeholders = ",".join("?" for _ in self._last_scanned_files)
        query = (
            f"SELECT {self._METADATA_COLUMNS} FROM screenshot_metadata "  # noqa: S608 - placeholders は "?" のみ
            f"WHERE filename IN ({placeholders}) ORDER BY max_count DESC LIMIT 1"
        )
        with sqlite3.connect(self.cache_path) as conn:
            row = conn.execute(query, self._last_scanned_files).fetchone()

        return self._row_to_metadata(row) if row is not None else None

    def get_representative_screenshot_for_earthquake(
        self, event_id: str
    ) -> rsudp.types.ScreenshotMetadata | None:
        """
        指定した地震に関連付けられたスクリーンショットのうち max_count が最大の 1 枚を返す.

        事前計算済みの earthquake_event_id（update_earthquake_associations の結果）を参照する。
        該当スクリーンショットが無い（自局で検出していない）場合は None を返す。
        """
        query = (
            f"SELECT {self._METADATA_COLUMNS} FROM screenshot_metadata "  # noqa: S608 - 列名は定数
            "WHERE earthquake_event_id = ? ORDER BY max_count DESC LIMIT 1"
        )
        with sqlite3.connect(self.cache_path) as conn:
            row = conn.execute(query, (event_id,)).fetchone()

        return self._row_to_metadata(row) if row is not None else None
