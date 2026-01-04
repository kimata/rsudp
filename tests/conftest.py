"""
共通テストフィクスチャ

テスト全体で使用する共通のフィクスチャとヘルパーを定義します。
"""

import logging
import sqlite3
import tempfile
import unittest.mock
import zoneinfo
from datetime import datetime
from pathlib import Path

import pytest

import rsudp.config

# === 定数 ===
CONFIG_FILE = "config.yaml"
JST = zoneinfo.ZoneInfo("Asia/Tokyo")


# === 環境モック ===
@pytest.fixture(scope="session", autouse=True)
def env_mock():
    """テスト環境用の環境変数モック"""
    with unittest.mock.patch.dict(
        "os.environ",
        {
            "TEST": "true",
            "NO_COLORED_LOGS": "true",
        },
    ) as fixture:
        yield fixture


# === 一時ディレクトリ ===
@pytest.fixture
def temp_dir():
    """一時ディレクトリを提供するフィクスチャ."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# === 設定フィクスチャ ===
@pytest.fixture
def config(temp_dir):
    """テスト用の設定を提供するフィクスチャ."""
    screenshot_dir = temp_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    return rsudp.config.Config(
        plot=rsudp.config.PlotConfig(
            screenshot=rsudp.config.ScreenshotConfig(path=screenshot_dir),
        ),
        data=rsudp.config.DataConfig(
            cache=temp_dir / "cache.db",
            quake=temp_dir / "quake.db",
            selenium=temp_dir / "selenium",
        ),
        webapp=rsudp.config.WebappConfig(
            static_dir_path=temp_dir / "static",
        ),
        base_dir=temp_dir,
    )


@pytest.fixture
def screenshot_config(temp_dir):
    """スクリーンショットマネージャー用のテスト設定."""
    screenshot_dir = temp_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    return rsudp.config.Config(
        plot=rsudp.config.PlotConfig(
            screenshot=rsudp.config.ScreenshotConfig(path=screenshot_dir),
        ),
        data=rsudp.config.DataConfig(
            cache=temp_dir / "cache.db",
            quake=temp_dir / "quake.db",
            selenium=temp_dir / "selenium",
        ),
        webapp=rsudp.config.WebappConfig(
            static_dir_path=temp_dir / "static",
        ),
        base_dir=temp_dir,
    )


# === データベースフィクスチャ ===
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


# === データベーステスト用フィクスチャ ===
@pytest.fixture
def quake_db_config(temp_dir):
    """地震データベーステスト用の最小設定を提供するフィクスチャ."""
    return rsudp.config.Config(
        plot=rsudp.config.PlotConfig(
            screenshot=rsudp.config.ScreenshotConfig(path=temp_dir / "screenshots"),
        ),
        data=rsudp.config.DataConfig(
            cache=temp_dir / "cache.db",
            quake=temp_dir / "test.db",
            selenium=temp_dir / "selenium",
        ),
        webapp=rsudp.config.WebappConfig(
            static_dir_path=temp_dir / "static",
        ),
        base_dir=temp_dir,
    )


# === サンプルデータフィクスチャ ===
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
def sample_screenshot_metadata():
    """サンプルスクリーンショットメタデータ."""
    return {
        "filename": "SHAKE-2025-12-12-190500.png",
        "filepath": "2025/12/12/SHAKE-2025-12-12-190500.png",
        "year": 2025,
        "month": 12,
        "day": 12,
        "hour": 19,
        "minute": 5,
        "second": 0,
        "timestamp": "2025-12-12T19:05:00+00:00",
        "sta_value": 100.0,
        "lta_value": 50.0,
        "sta_lta_ratio": 2.0,
        "max_count": 1000.0,
        "created_at": 1234567890.0,
        "file_size": 12345,
        "metadata_raw": "STA=100.0, LTA=50.0, STA/LTA=2.0, MaxCount=1000",
    }


# === Flask アプリフィクスチャ ===
@pytest.fixture
def flask_app(config):
    """Flask アプリケーションフィクスチャ."""
    import flask
    import flask_cors

    from rsudp.webui.api import viewer

    # グローバルなスクリーンショットマネージャーをリセット
    viewer._screenshot_manager = None

    app = flask.Flask(__name__)
    flask_cors.CORS(app)

    app.config["CONFIG"] = config
    app.config["TESTING"] = True

    # Blueprint を登録
    app.register_blueprint(viewer.blueprint)

    return app


@pytest.fixture
def flask_client(flask_app):
    """Flask テストクライアント."""
    return flask_app.test_client()


# === ロギング設定 ===
logging.getLogger("werkzeug").setLevel(logging.WARNING)
