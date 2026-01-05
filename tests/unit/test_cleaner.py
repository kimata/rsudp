#!/usr/bin/env python3
# ruff: noqa: S101
"""
cleaner.py のテスト
"""

import sqlite3
from datetime import datetime, timedelta, timezone

import cleaner


class TestGetScreenshotsToClean:
    """get_screenshots_to_clean のテスト"""

    def test_no_screenshots_to_delete(self, config, temp_dir):
        """削除対象がない場合"""
        # 空のキャッシュDBを作成
        cache_db_path = config.data.cache
        with sqlite3.connect(cache_db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS screenshot_metadata (
                    filename TEXT PRIMARY KEY,
                    filepath TEXT,
                    timestamp TEXT,
                    max_count REAL
                )
            """)

        # 空の地震DBを作成
        quake_db_path = config.data.quake
        with sqlite3.connect(quake_db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS earthquakes (
                    detected_at TEXT,
                    epicenter_name TEXT,
                    magnitude REAL
                )
            """)

        result = cleaner.get_screenshots_to_clean(config)
        assert result == []

    def test_screenshot_with_nearby_earthquake(self, config, temp_dir):
        """近くに地震がある場合は削除対象にならない"""
        jst = timezone(timedelta(hours=9))
        now = datetime.now(jst)

        # キャッシュDBを作成
        cache_db_path = config.data.cache
        with sqlite3.connect(cache_db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS screenshot_metadata (
                    filename TEXT PRIMARY KEY,
                    filepath TEXT,
                    timestamp TEXT,
                    max_count REAL
                )
            """)
            conn.execute(
                "INSERT INTO screenshot_metadata VALUES (?, ?, ?, ?)",
                ("test.png", "test.png", now.isoformat(), 400000),
            )

        # 地震DBを作成（同時刻に地震あり）
        quake_db_path = config.data.quake
        with sqlite3.connect(quake_db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS earthquakes (
                    detected_at TEXT,
                    epicenter_name TEXT,
                    magnitude REAL
                )
            """)
            conn.execute(
                "INSERT INTO earthquakes VALUES (?, ?, ?)",
                (now.isoformat(), "東京都", 5.0),
            )

        result = cleaner.get_screenshots_to_clean(config)
        assert result == []

    def test_screenshot_without_nearby_earthquake(self, config, temp_dir):
        """近くに地震がない場合は削除対象になる"""
        jst = timezone(timedelta(hours=9))
        now = datetime.now(jst)
        # 1時間前の地震（時間窓外）
        quake_time = now - timedelta(hours=1)

        # キャッシュDBを作成
        cache_db_path = config.data.cache
        with sqlite3.connect(cache_db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS screenshot_metadata (
                    filename TEXT PRIMARY KEY,
                    filepath TEXT,
                    timestamp TEXT,
                    max_count REAL
                )
            """)
            conn.execute(
                "INSERT INTO screenshot_metadata VALUES (?, ?, ?, ?)",
                ("test.png", "test.png", now.isoformat(), 400000),
            )

        # 地震DBを作成（時間窓外）
        quake_db_path = config.data.quake
        with sqlite3.connect(quake_db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS earthquakes (
                    detected_at TEXT,
                    epicenter_name TEXT,
                    magnitude REAL
                )
            """)
            conn.execute(
                "INSERT INTO earthquakes VALUES (?, ?, ?)",
                (quake_time.isoformat(), "東京都", 5.0),
            )

        result = cleaner.get_screenshots_to_clean(config)
        assert len(result) == 1
        assert result[0]["filename"] == "test.png"


class TestRemoveEmptyDirectories:
    """_remove_empty_directories のテスト"""

    def test_remove_empty_directory(self, temp_dir):
        """空のディレクトリが削除される"""
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()

        count = cleaner._remove_empty_directories(temp_dir)

        assert count == 1
        assert not empty_dir.exists()

    def test_dry_run_mode(self, temp_dir):
        """dry-run モードでは削除されない"""
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()

        count = cleaner._remove_empty_directories(temp_dir, dry_run=True)

        assert count == 1
        assert empty_dir.exists()

    def test_non_empty_directory_not_removed(self, temp_dir):
        """空でないディレクトリは削除されない"""
        non_empty_dir = temp_dir / "non_empty"
        non_empty_dir.mkdir()
        (non_empty_dir / "file.txt").write_text("content")

        count = cleaner._remove_empty_directories(temp_dir)

        assert count == 0
        assert non_empty_dir.exists()


class TestDeleteScreenshots:
    """delete_screenshots のテスト"""

    def test_delete_screenshot_dry_run(self, config, temp_dir):
        """dry-run モードではファイルが削除されない"""
        jst = timezone(timedelta(hours=9))
        now = datetime.now(jst)

        # テストファイルを作成
        screenshot_dir = config.plot.screenshot.path
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        test_file = screenshot_dir / "test.png"
        test_file.write_text("test")

        # キャッシュDBを作成
        cache_db_path = config.data.cache
        with sqlite3.connect(cache_db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS screenshot_metadata (
                    filename TEXT PRIMARY KEY
                )
            """)
            conn.execute("INSERT INTO screenshot_metadata VALUES (?)", ("test.png",))

        to_delete = [
            {
                "filename": "test.png",
                "filepath": "test.png",
                "timestamp": now,
                "max_count": 400000,
            }
        ]

        count = cleaner.delete_screenshots(config, to_delete, dry_run=True)

        assert count == 1
        assert test_file.exists()

    def test_delete_screenshot(self, config, temp_dir):
        """ファイルが削除される"""
        jst = timezone(timedelta(hours=9))
        now = datetime.now(jst)

        # テストファイルを作成
        screenshot_dir = config.plot.screenshot.path
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        test_file = screenshot_dir / "test.png"
        test_file.write_text("test")

        # キャッシュDBを作成
        cache_db_path = config.data.cache
        with sqlite3.connect(cache_db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS screenshot_metadata (
                    filename TEXT PRIMARY KEY
                )
            """)
            conn.execute("INSERT INTO screenshot_metadata VALUES (?)", ("test.png",))

        to_delete = [
            {
                "filename": "test.png",
                "filepath": "test.png",
                "timestamp": now,
                "max_count": 400000,
            }
        ]

        count = cleaner.delete_screenshots(config, to_delete, dry_run=False)

        assert count == 1
        assert not test_file.exists()

    def test_delete_nonexistent_file(self, config, temp_dir):
        """存在しないファイルの削除"""
        jst = timezone(timedelta(hours=9))
        now = datetime.now(jst)

        # キャッシュDBを作成
        cache_db_path = config.data.cache
        with sqlite3.connect(cache_db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS screenshot_metadata (
                    filename TEXT PRIMARY KEY
                )
            """)
            conn.execute("INSERT INTO screenshot_metadata VALUES (?)", ("nonexistent.png",))

        to_delete = [
            {
                "filename": "nonexistent.png",
                "filepath": "nonexistent.png",
                "timestamp": now,
                "max_count": 400000,
            }
        ]

        # エラーなく完了
        count = cleaner.delete_screenshots(config, to_delete, dry_run=False)
        assert count == 1


class TestRunCleaner:
    """_run_cleaner のテスト"""

    def test_run_cleaner_no_targets(self, config, temp_dir):
        """削除対象がない場合"""
        # 空のキャッシュDBを作成
        cache_db_path = config.data.cache
        with sqlite3.connect(cache_db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS screenshot_metadata (
                    filename TEXT PRIMARY KEY,
                    filepath TEXT,
                    timestamp TEXT,
                    max_count REAL
                )
            """)

        # 空の地震DBを作成
        quake_db_path = config.data.quake
        with sqlite3.connect(quake_db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS earthquakes (
                    detected_at TEXT,
                    epicenter_name TEXT,
                    magnitude REAL
                )
            """)

        count = cleaner._run_cleaner(config)
        assert count == 0

    def test_run_cleaner_dry_run(self, config, temp_dir):
        """dry-run モード"""
        jst = timezone(timedelta(hours=9))
        now = datetime.now(jst)

        # テストファイルを作成
        screenshot_dir = config.plot.screenshot.path
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        test_file = screenshot_dir / "test.png"
        test_file.write_text("test")

        # キャッシュDBを作成
        cache_db_path = config.data.cache
        with sqlite3.connect(cache_db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS screenshot_metadata (
                    filename TEXT PRIMARY KEY,
                    filepath TEXT,
                    timestamp TEXT,
                    max_count REAL
                )
            """)
            conn.execute(
                "INSERT INTO screenshot_metadata VALUES (?, ?, ?, ?)",
                ("test.png", "test.png", now.isoformat(), 400000),
            )

        # 空の地震DBを作成
        quake_db_path = config.data.quake
        with sqlite3.connect(quake_db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS earthquakes (
                    detected_at TEXT,
                    epicenter_name TEXT,
                    magnitude REAL
                )
            """)

        count = cleaner._run_cleaner(config, dry_run=True)
        assert count == 1
        assert test_file.exists()
