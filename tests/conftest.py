"""テスト用の共通フィクスチャ."""

import sqlite3
import tempfile
import zoneinfo
from datetime import datetime
from pathlib import Path

import pytest

JST = zoneinfo.ZoneInfo("Asia/Tokyo")


@pytest.fixture
def temp_dir():
    """一時ディレクトリを提供するフィクスチャ."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def quake_db(temp_dir):
    """テスト用の地震データベースを作成するフィクスチャ."""
    db_path = temp_dir / "quake.db"

    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS earthquakes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                detected_at TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                magnitude REAL NOT NULL,
                depth INTEGER NOT NULL,
                epicenter_name TEXT NOT NULL,
                max_intensity TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

    return db_path


@pytest.fixture
def sample_earthquake_jst():
    """JST タイムゾーンのサンプル地震データ."""
    # 2025-12-13 04:05:00 JST = 2025-12-12 19:05:00 UTC
    return {
        "event_id": "test-quake-001",
        "detected_at": datetime(2025, 12, 13, 4, 5, 0, tzinfo=JST),
        "latitude": 35.6,
        "longitude": 139.7,
        "magnitude": 4.5,
        "depth": 50,
        "epicenter_name": "東京都",
        "max_intensity": "3",
    }


@pytest.fixture
def screenshot_config(temp_dir):
    """スクリーンショットマネージャー用のテスト設定."""
    screenshot_dir = temp_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    return {
        "plot": {"screenshot": {"path": str(screenshot_dir)}},
        "data": {"cache": str(temp_dir / "cache.db")},
    }
