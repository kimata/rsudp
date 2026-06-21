# ruff: noqa: S101 S603 S607
"""compress モジュールのユニットテスト."""

import datetime
import shutil
import sqlite3
import subprocess

import numpy as np
import obspy
import pytest

import rsudp.compress
import rsudp.schema_util
import rsudp.types
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


# --- extract_earthquake_miniseed ---


def _make_miniseed_zst(data_dir, year, yday, *, channel="EHZ", center_hour=12, dur_seconds=3600, sr=1.0):
    """ダミーの全日 miniSEED（zstd 圧縮）を作成し、(パス, 中心時刻UTC) を返す."""
    day = obspy.UTCDateTime(year=year, julday=yday)
    center = day + center_hour * 3600
    start = center - dur_seconds / 2
    npts = int(dur_seconds * sr)
    tr = obspy.Trace(data=np.arange(npts, dtype=np.int32))
    tr.stats.network = "AM"
    tr.stats.station = "SHAKE"
    tr.stats.location = "00"
    tr.stats.channel = channel
    tr.stats.sampling_rate = sr
    tr.stats.starttime = start
    name = f"AM.SHAKE.00.{channel}.D.{year}.{yday:03d}"
    raw = data_dir / f"{name}.mseed"
    tr.write(str(raw), format="MSEED")
    zst = data_dir / f"{name}.zst"
    subprocess.run(["zstd", "-q", "-o", str(zst), str(raw)], check=True, capture_output=True)
    raw.unlink()
    return zst, center


def _insert_quake(quake_path, center_utc, magnitude):
    """extract が読む quake.db に地震を1件挿入する（detected_at は JST）."""
    jst = center_utc.datetime.replace(tzinfo=datetime.UTC).astimezone(rsudp.types.JST)
    with sqlite3.connect(quake_path) as conn:
        rsudp.schema_util.init_database(conn, "earthquakes")
        conn.execute(
            """INSERT INTO earthquakes
            (event_id, detected_at, latitude, longitude, magnitude, depth,
             epicenter_name, max_intensity, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "eq1",
                jst.isoformat(),
                35.0,
                139.0,
                magnitude,
                10,
                "テスト",
                "3",
                "2025-01-01T00:00:00+00:00",
                "2025-01-01T00:00:00+00:00",
            ),
        )
        conn.commit()


def test_after_seconds_for_magnitude():
    assert rsudp.compress._after_seconds_for_magnitude(4.0) == 600
    assert rsudp.compress._after_seconds_for_magnitude(5.5) == 1200
    assert rsudp.compress._after_seconds_for_magnitude(7.0) == 1800


@pytest.mark.skipif(not _HAS_ZSTD, reason="zstd が未インストール")
def test_extract_basic(tmp_path):
    """地震該当日の miniSEED から区間が抽出され .eq.zst になること."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    zst, center = _make_miniseed_zst(data_dir, 2025, 300)
    quake_path = tmp_path / "quake.db"
    _insert_quake(quake_path, center, 4.5)
    orig = zst.stat().st_size

    result = rsudp.compress.extract_earthquake_miniseed(data_dir, quake_path)

    assert result.processed == 1
    assert not zst.exists()
    eq = data_dir / "AM.SHAKE.00.EHZ.D.2025.300.eq.zst"
    assert eq.exists()
    assert eq.stat().st_size < orig


@pytest.mark.skipif(not _HAS_ZSTD, reason="zstd が未インストール")
def test_extract_deletes_non_matching(tmp_path):
    """地震に該当しない日のファイルは削除されること."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    zst, _ = _make_miniseed_zst(data_dir, 2025, 300)
    quake_path = tmp_path / "quake.db"
    # 別の日（yday=100）に地震 → yday=300 のファイルは非該当
    other = obspy.UTCDateTime(year=2025, julday=100) + 12 * 3600
    _insert_quake(quake_path, other, 4.5)

    result = rsudp.compress.extract_earthquake_miniseed(data_dir, quake_path)

    assert result.deleted == 1
    assert not zst.exists()


@pytest.mark.skipif(not _HAS_ZSTD, reason="zstd が未インストール")
def test_extract_idempotent(tmp_path):
    """抽出済み（.eq.zst）は再処理しないこと."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "AM.SHAKE.00.EHZ.D.2025.300.eq.zst").write_bytes(b"already extracted")
    quake_path = tmp_path / "quake.db"
    _insert_quake(quake_path, obspy.UTCDateTime(year=2025, julday=300) + 43200, 4.5)

    result = rsudp.compress.extract_earthquake_miniseed(data_dir, quake_path)

    assert result.processed == 0
    assert result.deleted == 0


@pytest.mark.skipif(not _HAS_ZSTD, reason="zstd が未インストール")
def test_extract_skips_recent(tmp_path):
    """確定待ちマージン内（最近）のファイルは対象外であること."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    today = datetime.datetime.now(datetime.UTC)
    zst, center = _make_miniseed_zst(data_dir, today.year, today.timetuple().tm_yday)
    quake_path = tmp_path / "quake.db"
    _insert_quake(quake_path, center, 4.5)

    result = rsudp.compress.extract_earthquake_miniseed(data_dir, quake_path)

    assert result.processed == 0
    assert result.deleted == 0
    assert zst.exists()


@pytest.mark.skipif(not _HAS_ZSTD, reason="zstd が未インストール")
def test_extract_dry_run(tmp_path):
    """dry-run ではファイルを変更しないこと."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    zst, center = _make_miniseed_zst(data_dir, 2025, 300)
    quake_path = tmp_path / "quake.db"
    _insert_quake(quake_path, center, 4.5)

    result = rsudp.compress.extract_earthquake_miniseed(data_dir, quake_path, dry_run=True)

    assert result.processed == 1
    assert zst.exists()
    assert not (data_dir / "AM.SHAKE.00.EHZ.D.2025.300.eq.zst").exists()
