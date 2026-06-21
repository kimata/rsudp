# ruff: noqa: S101
"""compress モジュールのユニットテスト."""

import datetime
import shutil
import sqlite3

import pytest

import rsudp.compress
import rsudp.schema_util
from tests.helpers import insert_screenshot_metadata

_HAS_CWEBP = shutil.which("cwebp") is not None
_HAS_ZSTD = shutil.which("zstd") is not None


def _make_miniseed(directory, name, size=4096):
    """ダミーの miniSEED ファイルを作成する."""
    path = directory / name
    # zstd で圧縮可能なように繰り返しデータを書き込む
    path.write_bytes(b"SEISMIC\x00" * (size // 8))
    return path


def _make_cache_db(path):
    """screenshot_metadata テーブルを持つキャッシュ DB を作成する."""
    with sqlite3.connect(path) as conn:
        rsudp.schema_util.init_database(conn, "screenshot_metadata")
    return path


# --- CompressResult ---


def test_compress_result_saved():
    result = rsudp.compress.CompressResult(bytes_before=100, bytes_after=30)
    assert result.saved == 70


# --- compress_miniseed ---


@pytest.mark.skipif(not _HAS_ZSTD, reason="zstd が未インストール")
def test_compress_miniseed_past_day(tmp_path):
    """前日以前の miniSEED が zstd 圧縮されること."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    src = _make_miniseed(data_dir, "AM.SHAKE.00.ENZ.D.2020.001")

    result = rsudp.compress.compress_miniseed(data_dir)

    assert result.processed == 1
    assert not src.exists()
    assert (data_dir / "AM.SHAKE.00.ENZ.D.2020.001.zst").exists()
    assert result.saved > 0


def test_compress_miniseed_excludes_today(tmp_path):
    """当日のファイルは書き込み中の可能性があるため圧縮しないこと."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    now = datetime.datetime.now(datetime.UTC)
    name = f"AM.SHAKE.00.ENZ.D.{now.year}.{now.timetuple().tm_yday:03d}"
    src = _make_miniseed(data_dir, name)

    result = rsudp.compress.compress_miniseed(data_dir)

    assert result.processed == 0
    assert src.exists()


def test_compress_miniseed_idempotent(tmp_path):
    """既に .zst のファイルは再処理しないこと."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "AM.SHAKE.00.ENZ.D.2020.001.zst").write_bytes(b"already compressed")

    result = rsudp.compress.compress_miniseed(data_dir)

    assert result.processed == 0


def test_compress_miniseed_ignores_unrelated_files(tmp_path):
    """miniSEED 命名規則に合致しないファイルは無視すること."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    other = data_dir / "README.txt"
    other.write_bytes(b"not miniseed")

    result = rsudp.compress.compress_miniseed(data_dir)

    assert result.processed == 0
    assert other.exists()


def test_compress_miniseed_dry_run(tmp_path):
    """dry-run ではファイルを変更しないこと."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    src = _make_miniseed(data_dir, "AM.SHAKE.00.ENZ.D.2020.001")

    result = rsudp.compress.compress_miniseed(data_dir, dry_run=True)

    assert result.processed == 1
    assert src.exists()
    assert not (data_dir / "AM.SHAKE.00.ENZ.D.2020.001.zst").exists()


@pytest.mark.skipif(not _HAS_ZSTD, reason="zstd が未インストール")
def test_miniseed_roundtrip(tmp_path):
    """圧縮 → 展開で元のデータが復元できること（可逆性）."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    original = b"hello seismic data " * 256
    src = data_dir / "AM.SHAKE.00.ENZ.D.2020.001"
    src.write_bytes(original)

    rsudp.compress.compress_miniseed(data_dir)
    zst = data_dir / "AM.SHAKE.00.ENZ.D.2020.001.zst"
    assert zst.exists()

    restored = rsudp.compress.decompress_miniseed(zst)

    assert restored.read_bytes() == original
    assert not zst.exists()


# --- convert_screenshots ---


def test_convert_screenshots_dry_run(tmp_path):
    """dry-run では PNG も DB も変更しないこと."""
    screenshot_dir = tmp_path / "screenshots"
    day_dir = screenshot_dir / "2025" / "12" / "12"
    day_dir.mkdir(parents=True)
    rel = "2025/12/12/SHAKE-2025-12-12-190500.png"
    png = screenshot_dir / rel
    png.write_bytes(b"fake png data" * 10)

    cache_path = _make_cache_db(tmp_path / "cache.db")
    with sqlite3.connect(cache_path) as conn:
        insert_screenshot_metadata(conn, filepath=rel, file_size=png.stat().st_size)
        conn.commit()

    result = rsudp.compress.convert_screenshots(screenshot_dir, cache_path, dry_run=True)

    assert result.processed == 1
    assert png.exists()
    with sqlite3.connect(cache_path) as conn:
        filename = conn.execute("SELECT filename FROM screenshot_metadata").fetchone()[0]
    assert filename.endswith(".png")


@pytest.mark.skipif(not _HAS_CWEBP, reason="cwebp が未インストール")
def test_convert_screenshots(tmp_path):
    """PNG が WebP に変換され、cache.db が更新されること."""
    import PIL.Image

    screenshot_dir = tmp_path / "screenshots"
    day_dir = screenshot_dir / "2025" / "12" / "12"
    day_dir.mkdir(parents=True)
    rel = "2025/12/12/SHAKE-2025-12-12-190500.png"
    png = screenshot_dir / rel
    PIL.Image.new("RGB", (200, 200), "white").save(png)

    cache_path = _make_cache_db(tmp_path / "cache.db")
    with sqlite3.connect(cache_path) as conn:
        insert_screenshot_metadata(conn, filepath=rel, file_size=png.stat().st_size)
        conn.commit()

    result = rsudp.compress.convert_screenshots(screenshot_dir, cache_path)

    assert result.processed == 1
    assert not png.exists()
    assert (day_dir / "SHAKE-2025-12-12-190500.webp").exists()

    with sqlite3.connect(cache_path) as conn:
        row = conn.execute("SELECT filename, filepath FROM screenshot_metadata").fetchone()
    assert row[0] == "SHAKE-2025-12-12-190500.webp"
    assert row[1].endswith(".webp")
