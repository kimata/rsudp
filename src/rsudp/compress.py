"""
data ディレクトリの圧縮ユーティリティ.

ディスク使用量を削減するため、以下の 2 種類のデータを圧縮する:

- miniSEED 波形アーカイブ（data/data）を zstd で圧縮保持する（アプリ非参照）
- スクリーンショット PNG を WebP（lossy q95 + sharp_yuv）に変換する

外部バイナリ ``zstd`` / ``cwebp`` を subprocess 経由で利用する。
スクリーンショットのメタデータ（STA/LTA 等）は cache.db が真実のソースであり、
変換時に cache.db の filename/filepath/file_size を WebP のものへ更新する。
"""

# subprocess は固定の信頼できるコマンド（zstd / cwebp）のみを実行するため S603/S607 を抑制する
# ruff: noqa: S603 S607

from __future__ import annotations

import dataclasses
import datetime
import logging
import re
import shutil
import sqlite3
import subprocess
from pathlib import Path

# miniSEED ファイル名フォーマット: NET.STA.LOC.CHAN.D.YYYY.DDD
# 例: AM.SHAKE.00.ENZ.D.2026.010
_MINISEED_PATTERN = re.compile(r"\.D\.(\d{4})\.(\d{3})$")

ZSTD_LEVEL = 19
WEBP_QUALITY = 95


@dataclasses.dataclass
class CompressResult:
    """圧縮処理の結果."""

    processed: int = 0
    skipped: int = 0
    bytes_before: int = 0
    bytes_after: int = 0

    @property
    def saved(self) -> int:
        """削減バイト数."""
        return self.bytes_before - self.bytes_after


def _check_binary(name: str) -> bool:
    """外部バイナリの存在を確認する."""
    if shutil.which(name) is None:
        logging.error("%s が見つかりません。インストールが必要です", name)
        return False
    return True


def _is_past_day(year: int, yday: int, now: datetime.datetime) -> bool:
    """指定の年・通日が当日より前か判定する（当日は書き込み中の可能性があるため除外）."""
    return (year, yday) < (now.year, now.timetuple().tm_yday)


def compress_miniseed(
    data_dir: Path,
    *,
    level: int = ZSTD_LEVEL,
    dry_run: bool = False,
) -> CompressResult:
    """
    miniSEED 波形アーカイブを zstd で圧縮する.

    data_dir 直下の未圧縮ファイルのうち、ファイル名の年・通日が前日以前のものを
    対象に ``*.zst`` へ圧縮する（元ファイルは削除）。当日のファイルは rsudp が
    書き込み中の可能性があるため対象外とする。冪等（既に .zst のものは再処理しない）。

    Args:
        data_dir: miniSEED アーカイブのディレクトリ
        level: zstd 圧縮レベル
        dry_run: True の場合、実際には圧縮しない

    Returns:
        圧縮結果

    """
    result = CompressResult()

    if not data_dir.exists():
        logging.warning("miniSEED ディレクトリが存在しません: %s", data_dir)
        return result
    if not dry_run and not _check_binary("zstd"):
        return result

    now = datetime.datetime.now(datetime.UTC)

    for path in sorted(data_dir.iterdir()):
        if not path.is_file() or path.suffix == ".zst":
            continue

        match = _MINISEED_PATTERN.search(path.name)
        if not match:
            continue

        year, yday = int(match.group(1)), int(match.group(2))
        if not _is_past_day(year, yday, now):
            # 当日（以降）のファイルは書き込み中の可能性があるためスキップ
            continue

        before = path.stat().st_size

        if dry_run:
            logging.info("[dry-run] zstd 圧縮対象: %s (%d bytes)", path.name, before)
            result.processed += 1
            result.bytes_before += before
            continue

        try:
            subprocess.run(
                ["zstd", f"-{level}", "-T0", "-q", "--rm", str(path)],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError:
            logging.warning("zstd 圧縮失敗: %s", path)
            result.skipped += 1
            continue

        after = (path.parent / (path.name + ".zst")).stat().st_size
        logging.info("zstd 圧縮: %s (%d -> %d bytes)", path.name, before, after)
        result.processed += 1
        result.bytes_before += before
        result.bytes_after += after

    return result


def decompress_miniseed(path: Path) -> Path:
    """
    zstd 圧縮された miniSEED ファイルを展開する.

    Args:
        path: ``*.zst`` ファイルのパス

    Returns:
        展開後のファイルパス

    """
    if path.suffix != ".zst":
        msg = f"zstd ファイルではありません: {path}"
        raise ValueError(msg)
    if not _check_binary("zstd"):
        msg = "zstd が見つかりません"
        raise RuntimeError(msg)

    subprocess.run(["zstd", "-d", "-q", "--rm", str(path)], check=True, capture_output=True)
    return path.parent / path.stem


def convert_screenshots(
    screenshot_dir: Path,
    cache_path: Path,
    *,
    quality: int = WEBP_QUALITY,
    dry_run: bool = False,
) -> CompressResult:
    """
    スクリーンショット PNG を WebP（lossy + sharp_yuv）へ変換する.

    cache.db に登録済みの ``*.png`` を対象に cwebp で WebP へ変換し、変換後は
    cache.db の filename/filepath/file_size を WebP のものへ更新して元 PNG を削除する。
    変換に失敗したファイルは PNG のまま残してスキップする。

    Args:
        screenshot_dir: スクリーンショットのルートディレクトリ
        cache_path: メタデータキャッシュ DB のパス
        quality: WebP の品質（lossy）
        dry_run: True の場合、実際には変換しない

    Returns:
        変換結果

    """
    result = CompressResult()

    if not cache_path.exists():
        logging.warning("キャッシュ DB が存在しません: %s", cache_path)
        return result
    if not dry_run and not _check_binary("cwebp"):
        return result

    # webui の BackgroundMonitor が同じ cache.db を周期的に更新するため、
    # ロック競合に備えて busy_timeout を長めに設定する
    with sqlite3.connect(cache_path, timeout=30) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT filename, filepath FROM screenshot_metadata WHERE filename LIKE '%.png'"
        ).fetchall()

        for row in rows:
            src = screenshot_dir / row["filepath"]
            if not src.exists():
                result.skipped += 1
                continue

            before = src.stat().st_size
            dst = src.with_suffix(".webp")

            if dry_run:
                logging.info("[dry-run] WebP 変換対象: %s (%d bytes)", row["filename"], before)
                result.processed += 1
                result.bytes_before += before
                continue

            try:
                subprocess.run(
                    [
                        "cwebp",
                        "-quiet",
                        "-q",
                        str(quality),
                        "-sharp_yuv",
                        "-metadata",
                        "all",
                        str(src),
                        "-o",
                        str(dst),
                    ],
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError:
                logging.warning("cwebp 変換失敗: %s", src)
                result.skipped += 1
                continue

            after = dst.stat().st_size
            new_filename = dst.name
            new_filepath = str(dst.relative_to(screenshot_dir))

            # cache.db を WebP のメタデータへ更新（filename は PRIMARY KEY）
            conn.execute(
                "UPDATE screenshot_metadata SET filename = ?, filepath = ?, file_size = ? WHERE filename = ?",
                (new_filename, new_filepath, after, row["filename"]),
            )
            src.unlink()

            logging.info("WebP 変換: %s (%d -> %d bytes)", row["filename"], before, after)
            result.processed += 1
            result.bytes_before += before
            result.bytes_after += after

        if not dry_run:
            conn.commit()

    return result
