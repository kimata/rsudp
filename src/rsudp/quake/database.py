"""
地震データの SQLite データベース管理モジュール.

タイムゾーンの扱い:
    - detected_at (発生時刻): 気象庁 API から取得した JST (+09:00) で保存
    - created_at, updated_at: UTC で保存
    - 検索時は Python の datetime オブジェクト（タイムゾーン情報付き）で比較
"""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

# スキーマファイルのパス（プロジェクトルートからの相対パス）
SCHEMA_FILE = Path(__file__).parent.parent.parent.parent / "schema" / "sqlite.schema"


class QuakeDatabase:
    """地震データの SQLite ストレージを管理するクラス."""

    def __init__(self, config: dict):
        """設定を使用してデータベースを初期化する."""
        self.config = config
        self.db_path = Path(config.get("data", {}).get("quake", "data/quake.db"))

        # ディレクトリを作成
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # データベースを初期化
        self._init_database()

    def _init_database(self):
        """地震データ用の SQLite データベースを初期化する."""
        with sqlite3.connect(self.db_path) as conn:
            # スキーマファイルを読み込んで実行
            schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
            conn.executescript(schema_sql)

    def insert_earthquake(  # noqa: PLR0913
        self,
        event_id: str,
        detected_at: datetime,
        latitude: float,
        longitude: float,
        magnitude: float,
        depth: int,
        epicenter_name: str,
        max_intensity: str | None = None,
    ) -> bool:
        """
        地震データを挿入または更新する.

        Args:
            event_id: 地震イベントの一意識別子
            detected_at: 発生時刻（タイムゾーン情報付き datetime）
            latitude: 震源の緯度
            longitude: 震源の経度
            magnitude: マグニチュード
            depth: 震源の深さ (km)
            epicenter_name: 震源地名
            max_intensity: 最大震度（文字列）

        Returns:
            新規レコードが挿入された場合は True、更新された場合は False

        """
        now = datetime.now(tz=UTC).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            # レコードが存在するか確認
            cursor = conn.execute("SELECT id FROM earthquakes WHERE event_id = ?", (event_id,))
            existing = cursor.fetchone()

            if existing:
                # 既存レコードを更新
                conn.execute(
                    """
                    UPDATE earthquakes SET
                        detected_at = ?,
                        latitude = ?,
                        longitude = ?,
                        magnitude = ?,
                        depth = ?,
                        epicenter_name = ?,
                        max_intensity = ?,
                        updated_at = ?
                    WHERE event_id = ?
                """,
                    (
                        detected_at.isoformat(),
                        latitude,
                        longitude,
                        magnitude,
                        depth,
                        epicenter_name,
                        max_intensity,
                        now,
                        event_id,
                    ),
                )
                return False

            # 新規レコードを挿入
            conn.execute(
                """
                INSERT INTO earthquakes
                (event_id, detected_at, latitude, longitude, magnitude,
                 depth, epicenter_name, max_intensity, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    event_id,
                    detected_at.isoformat(),
                    latitude,
                    longitude,
                    magnitude,
                    depth,
                    epicenter_name,
                    max_intensity,
                    now,
                    now,
                ),
            )
            return True

    def get_earthquake_for_timestamp(
        self,
        timestamp: datetime,
        before_seconds: int = 30,
        after_seconds: int = 240,
    ) -> dict | None:
        """
        指定されたタイムスタンプに該当する地震を取得する.

        タイムスタンプが [地震発生時刻 - before_seconds, 地震発生時刻 + after_seconds]
        の範囲内であれば該当とみなす.

        Args:
            timestamp: 検索するタイムスタンプ（タイムゾーン情報付き datetime）
            before_seconds: 地震発生前の許容秒数（デフォルト: 30）
            after_seconds: 地震発生後の許容秒数（デフォルト: 240 = 4分）

        Returns:
            地震データの辞書、または見つからない場合は None

        """
        # 地震データを取得
        earthquakes = self.get_all_earthquakes(limit=1000)

        # Python で時間範囲の比較を行う（タイムゾーン情報付き datetime で正しく比較）
        best_match = None
        best_diff = None

        for eq in earthquakes:
            detected_at = datetime.fromisoformat(eq["detected_at"])
            start_time = detected_at - timedelta(seconds=before_seconds)
            end_time = detected_at + timedelta(seconds=after_seconds)

            if start_time <= timestamp <= end_time:
                # 時間差の絶対値を計算
                diff = abs((timestamp - detected_at).total_seconds())
                if best_diff is None or diff < best_diff:
                    best_diff = diff
                    best_match = eq

        return best_match

    def get_all_earthquakes(self, limit: int = 100) -> list[dict]:
        """すべての地震データを発生時刻の降順で取得する."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM earthquakes
                ORDER BY detected_at DESC
                LIMIT ?
            """,
                (limit,),
            )

            return [dict(row) for row in cursor.fetchall()]

    def get_earthquake_time_ranges(
        self,
        before_seconds: int = 30,
        after_seconds: int = 240,
    ) -> list[tuple[datetime, datetime, dict]]:
        """
        すべての地震の時間範囲を取得する.

        Returns:
            (開始時刻, 終了時刻, 地震データ) のタプルのリスト

        """
        earthquakes = self.get_all_earthquakes(limit=1000)
        ranges = []

        for eq in earthquakes:
            detected_at = datetime.fromisoformat(eq["detected_at"])
            start_time = detected_at - timedelta(seconds=before_seconds)
            end_time = detected_at + timedelta(seconds=after_seconds)
            ranges.append((start_time, end_time, eq))

        return ranges

    def count_earthquakes(self) -> int:
        """データベース内の地震データの総数を取得する."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM earthquakes")
            return cursor.fetchone()[0]
