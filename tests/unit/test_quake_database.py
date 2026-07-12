# ruff: noqa: S101
"""
QuakeDatabase のユニットテスト.

地震データベースの基本機能をテストします。
"""

from datetime import UTC, datetime

import rsudp.types
from rsudp.quake.database import QuakeDatabase


class TestQuakeDatabaseInit:
    """QuakeDatabase 初期化のテスト."""

    def test_init_creates_database(self, quake_db_config):
        """データベースファイルが作成されることを確認."""
        db = QuakeDatabase(quake_db_config)

        assert db.db_path.exists()

    def test_init_creates_tables(self, quake_db_config):
        """earthquakes テーブルが作成されることを確認."""
        import sqlite3

        QuakeDatabase(quake_db_config)

        with sqlite3.connect(quake_db_config.data.quake) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='earthquakes'")
            result = cursor.fetchone()

        assert result is not None
        assert result[0] == "earthquakes"


class TestInsertEarthquake:
    """地震データ挿入のテスト."""

    def test_insert_new_earthquake(self, quake_db_config, sample_earthquake_jst):
        """新規地震データが正しく挿入されることを確認."""
        db = QuakeDatabase(quake_db_config)

        result = db.insert_earthquake(**sample_earthquake_jst)

        assert result is True
        assert db.count_earthquakes() == 1

    def test_insert_duplicate_returns_false(self, quake_db_config, sample_earthquake_jst):
        """重複する地震データの挿入で False が返されることを確認."""
        db = QuakeDatabase(quake_db_config)

        db.insert_earthquake(**sample_earthquake_jst)
        result = db.insert_earthquake(**sample_earthquake_jst)

        assert result is False
        assert db.count_earthquakes() == 1

    def test_insert_existing_is_preserved(self, quake_db_config, sample_earthquake_jst):
        """既存 event_id は上書きされず、先に挿入した報が保持されることを確認."""
        db = QuakeDatabase(quake_db_config)

        # 先に挿入した報（新報を想定）
        db.insert_earthquake(**sample_earthquake_jst)

        # JMA list.json は同一 eid の古い報も含む。同じ event_id で magnitude を変更しても
        # 上書きせず、先に挿入した値を保持する（ON CONFLICT DO NOTHING）。
        older_report = sample_earthquake_jst.copy()
        older_report["magnitude"] = 5.0

        result = db.insert_earthquake(**older_report)

        assert result is False
        earthquakes = db.get_all_earthquakes()
        assert len(earthquakes) == 1
        # 先に挿入した magnitude が保持される
        assert earthquakes[0].magnitude == sample_earthquake_jst["magnitude"]

    def test_insert_stores_detected_at_as_utc(self, quake_db_config, sample_earthquake_jst):
        """JST の detected_at が UTC に正規化されて保存されることを確認."""
        db = QuakeDatabase(quake_db_config)

        db.insert_earthquake(**sample_earthquake_jst)

        eq = db.get_all_earthquakes()[0]
        assert eq.detected_at.endswith("+00:00")
        # 同じ瞬間を指す（オフセット変換のみで情報は失われない）
        assert datetime.fromisoformat(eq.detected_at) == sample_earthquake_jst["detected_at"]


class TestDetectedAtMigration:
    """detected_at の UTC 正規化マイグレーションのテスト."""

    def test_migrate_jst_rows_to_utc(self, quake_db_config):
        """旧形式（JST +09:00）で保存された行が初期化時に UTC へ変換されることを確認."""
        import sqlite3

        db = QuakeDatabase(quake_db_config)

        # 旧実装と同じ JST 形式で直接挿入
        with sqlite3.connect(db.db_path) as conn:
            conn.execute(
                """
                INSERT INTO earthquakes
                (event_id, detected_at, latitude, longitude, magnitude,
                 depth, epicenter_name, max_intensity, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "legacy-jst-001",
                    "2025-12-13T04:05:00+09:00",
                    35.6,
                    139.7,
                    4.5,
                    50,
                    "茨城県南部",
                    "4",
                    "2025-12-12T19:10:00+00:00",
                    "2025-12-12T19:10:00+00:00",
                ),
            )

        # 再初期化でマイグレーションが走る
        db = QuakeDatabase(quake_db_config)

        eq = db.get_all_earthquakes()[0]
        assert eq.detected_at == "2025-12-12T19:05:00+00:00"

    def test_migrate_idempotent(self, quake_db_config, sample_earthquake_jst):
        """UTC 保存済みの行は再初期化しても変化しないことを確認."""
        db = QuakeDatabase(quake_db_config)
        db.insert_earthquake(**sample_earthquake_jst)
        before = db.get_all_earthquakes()[0].detected_at

        db = QuakeDatabase(quake_db_config)

        assert db.get_all_earthquakes()[0].detected_at == before


class TestGetEarthquakeForTimestamp:
    """タイムスタンプによる地震検索のテスト."""

    def test_find_earthquake_exact_time(self, quake_db_config, sample_earthquake_jst):
        """正確な時刻で地震を検索できることを確認."""
        db = QuakeDatabase(quake_db_config)
        db.insert_earthquake(**sample_earthquake_jst)

        # 地震発生時刻と同じ時刻（UTC 変換）
        search_time = datetime(2025, 12, 12, 19, 5, 0, tzinfo=UTC)
        result = db.get_earthquake_for_timestamp(search_time)

        assert result is not None
        assert result.event_id == "test-quake-001"

    def test_find_earthquake_within_window(self, quake_db_config, sample_earthquake_jst):
        """時間窓内で地震を検索できることを確認."""
        db = QuakeDatabase(quake_db_config)
        db.insert_earthquake(**sample_earthquake_jst)

        # 地震発生の 2 分後
        search_time = datetime(2025, 12, 12, 19, 7, 0, tzinfo=UTC)
        result = db.get_earthquake_for_timestamp(search_time)

        assert result is not None
        assert result.event_id == "test-quake-001"

    def test_no_match_outside_window(self, quake_db_config, sample_earthquake_jst):
        """時間窓外では地震が見つからないことを確認."""
        db = QuakeDatabase(quake_db_config)
        db.insert_earthquake(**sample_earthquake_jst)

        # 地震発生の 10 分後（デフォルト after_seconds=240 の範囲外）
        search_time = datetime(2025, 12, 12, 19, 15, 0, tzinfo=UTC)
        result = db.get_earthquake_for_timestamp(search_time)

        assert result is None

    def test_no_false_match_with_same_numbers(self, quake_db_config, sample_earthquake_jst):
        """同じ数字でもタイムゾーンが異なれば誤マッチしないことを確認."""
        db = QuakeDatabase(quake_db_config)
        db.insert_earthquake(**sample_earthquake_jst)

        # 同じ数字だが UTC（実際は 9 時間後）
        # 地震: 2025-12-13 04:05:00 JST
        # 検索: 2025-12-13 04:05:00 UTC = 2025-12-13 13:05:00 JST
        wrong_match_time = datetime(2025, 12, 13, 4, 5, 0, tzinfo=UTC)
        result = db.get_earthquake_for_timestamp(wrong_match_time)

        assert result is None


class TestGetAllEarthquakes:
    """全地震データ取得のテスト."""

    def test_get_all_earthquakes_empty(self, quake_db_config):
        """データがない場合は空のリストが返されることを確認."""
        db = QuakeDatabase(quake_db_config)

        result = db.get_all_earthquakes()

        assert result == []

    def test_get_all_earthquakes_ordered(self, quake_db_config):
        """地震データが発生時刻の降順で返されることを確認."""
        db = QuakeDatabase(quake_db_config)

        # 異なる時刻で 3 件挿入
        times = [
            datetime(2025, 12, 10, 10, 0, 0, tzinfo=rsudp.types.JST),
            datetime(2025, 12, 12, 10, 0, 0, tzinfo=rsudp.types.JST),
            datetime(2025, 12, 11, 10, 0, 0, tzinfo=rsudp.types.JST),
        ]
        for i, t in enumerate(times):
            db.insert_earthquake(
                event_id=f"quake-{i}",
                detected_at=t,
                latitude=35.0,
                longitude=139.0,
                magnitude=4.0,
                depth=10,
                epicenter_name="テスト",
            )

        result = db.get_all_earthquakes()

        # 発生時刻の降順（最新が先頭）
        assert result[0].event_id == "quake-1"  # 12/12
        assert result[1].event_id == "quake-2"  # 12/11
        assert result[2].event_id == "quake-0"  # 12/10

    def test_get_all_earthquakes_limit(self, quake_db_config):
        """limit パラメータが正しく機能することを確認."""
        db = QuakeDatabase(quake_db_config)

        # 5 件挿入
        for i in range(5):
            db.insert_earthquake(
                event_id=f"quake-{i}",
                detected_at=datetime(2025, 12, 10 + i, 10, 0, 0, tzinfo=rsudp.types.JST),
                latitude=35.0,
                longitude=139.0,
                magnitude=4.0,
                depth=10,
                epicenter_name="テスト",
            )

        result = db.get_all_earthquakes(limit=3)

        assert len(result) == 3


class TestGetEarthquakeTimeRanges:
    """地震時間範囲取得のテスト."""

    def test_get_earthquake_time_ranges(self, quake_db_config, sample_earthquake_jst):
        """地震時間範囲が正しく計算されることを確認."""
        db = QuakeDatabase(quake_db_config)
        db.insert_earthquake(**sample_earthquake_jst)

        ranges = db.get_earthquake_time_ranges()

        assert len(ranges) == 1
        start_time, end_time, eq = ranges[0]

        # デフォルト: before_seconds=30, after_seconds=240
        detected_at = datetime.fromisoformat(eq.detected_at)
        assert start_time < detected_at
        assert end_time > detected_at


class TestCountEarthquakes:
    """地震データ件数取得のテスト."""

    def test_count_earthquakes_empty(self, quake_db_config):
        """データがない場合は 0 が返されることを確認."""
        db = QuakeDatabase(quake_db_config)

        assert db.count_earthquakes() == 0

    def test_count_earthquakes(self, quake_db_config, sample_earthquake_jst):
        """正しい件数が返されることを確認."""
        db = QuakeDatabase(quake_db_config)
        db.insert_earthquake(**sample_earthquake_jst)

        assert db.count_earthquakes() == 1
