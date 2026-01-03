#!/usr/bin/env python3
"""
地震に関連しない高振幅スクリーンショットを削除するクリーナーです.

最大振幅が指定値以上で、前後指定時間以内に指定マグニチュード以上の
地震がないスクリーンショットを削除します。

Usage:
  cleaner.py [-c CONFIG] [-n] [-D] [--min-count=COUNT] [--time-window=MINUTES] [--min-mag=MAG]

Options:
  -c CONFIG               : 設定ファイルを指定します。[default: config.yaml]
  -n                      : dry-run モード。実際には削除せず、削除対象を表示します。
  -D                      : デバッグモードで動作します。
  --min-count=COUNT       : 最小振幅閾値を指定します。[default: 300000]
  --time-window=MINUTES   : 地震との時間窓（分）を指定します。[default: 10]
  --min-mag=MAG           : 最小マグニチュードを指定します。[default: 3.0]
"""

import logging
import pathlib
import sqlite3
from datetime import datetime, timedelta, timezone

import my_lib.config
import my_lib.logger

SCHEMA_CONFIG = "schema/config.schema"

# クリーナーのデフォルト設定
DEFAULT_MIN_MAX_COUNT = 300000  # 最小振幅閾値
DEFAULT_TIME_WINDOW_MINUTES = 10  # 地震との時間差（分）
DEFAULT_MIN_MAGNITUDE = 3.0  # 最小マグニチュード

JST = timezone(timedelta(hours=9))


def get_screenshots_to_clean(
    config: dict,
    min_max_count: float = DEFAULT_MIN_MAX_COUNT,
    time_window_minutes: int = DEFAULT_TIME_WINDOW_MINUTES,
    min_magnitude: float = DEFAULT_MIN_MAGNITUDE,
) -> list[dict]:
    """
    削除対象のスクリーンショットを取得する.

    Args:
        config: アプリケーション設定
        min_max_count: 最小振幅閾値
        time_window_minutes: 地震との時間差（分）
        min_magnitude: 最小マグニチュード

    Returns:
        削除対象のスクリーンショット情報のリスト

    """
    cache_db_path = pathlib.Path(config.get("data", {}).get("cache", "data/cache.db"))
    quake_db_path = pathlib.Path(config.get("data", {}).get("quake", "data/quake.db"))

    # スクリーンショット取得
    with sqlite3.connect(cache_db_path) as cache_db:
        cache_db.row_factory = sqlite3.Row
        screenshots = cache_db.execute(
            """
            SELECT filename, filepath, timestamp, max_count
            FROM screenshot_metadata
            WHERE max_count >= ?
            ORDER BY timestamp
            """,
            (min_max_count,),
        ).fetchall()

    # 地震データ取得
    with sqlite3.connect(quake_db_path) as quake_db:
        quake_db.row_factory = sqlite3.Row
        earthquakes = quake_db.execute(
            """
            SELECT detected_at, epicenter_name, magnitude
            FROM earthquakes
            WHERE magnitude >= ?
            """,
            (min_magnitude,),
        ).fetchall()

    # 地震の時刻をパース
    quake_times = []
    for eq in earthquakes:
        dt = datetime.fromisoformat(eq["detected_at"])
        quake_times.append((dt, eq["epicenter_name"], eq["magnitude"]))

    # 削除対象を特定
    time_window_seconds = time_window_minutes * 60
    to_delete = []

    for ss in screenshots:
        ss_time = datetime.fromisoformat(ss["timestamp"])
        ss_time_jst = ss_time.astimezone(JST)

        # 付近に地震があるか確認
        found_quake = None
        for qt, name, mag in quake_times:
            diff = abs((ss_time_jst - qt).total_seconds())
            if diff <= time_window_seconds:
                found_quake = (qt, name, mag, diff)
                break

        if not found_quake:
            to_delete.append(
                {
                    "filename": ss["filename"],
                    "filepath": ss["filepath"],
                    "timestamp": ss_time_jst,
                    "max_count": ss["max_count"],
                }
            )

    return to_delete


def remove_empty_directories(base_dir: pathlib.Path, *, dry_run: bool = False) -> int:
    """
    空のディレクトリを再帰的に削除する.

    Args:
        base_dir: 基準ディレクトリ
        dry_run: True の場合、実際には削除しない

    Returns:
        削除したディレクトリ数

    """
    removed_count = 0

    # 深い階層から順に処理するため、全ディレクトリを取得してソート
    all_dirs = sorted(base_dir.rglob("*"), key=lambda p: len(p.parts), reverse=True)

    for dir_path in all_dirs:
        if not dir_path.is_dir():
            continue

        # ディレクトリが空かどうか確認
        try:
            if not any(dir_path.iterdir()):
                if dry_run:
                    logging.info("[dry-run] 空ディレクトリ削除対象: %s", dir_path)
                else:
                    dir_path.rmdir()
                    logging.info("空ディレクトリ削除: %s", dir_path)
                removed_count += 1
        except OSError:
            # ディレクトリが空でない、またはアクセスエラー
            pass

    return removed_count


def delete_screenshots(config: dict, screenshots: list[dict], *, dry_run: bool = False) -> int:
    """
    スクリーンショットを削除する.

    Args:
        config: アプリケーション設定
        screenshots: 削除対象のスクリーンショット情報のリスト
        dry_run: True の場合、実際には削除しない

    Returns:
        削除した件数

    """
    cache_db_path = pathlib.Path(config.get("data", {}).get("cache", "data/cache.db"))
    screenshot_dir = pathlib.Path(config.get("data", {}).get("screenshot", "data/screenshots"))

    deleted_count = 0

    with sqlite3.connect(cache_db_path) as cache_db:
        for ss in screenshots:
            file_path = screenshot_dir / ss["filepath"]

            if dry_run:
                logging.info(
                    "[dry-run] 削除対象: %s (振幅: %d, 時刻: %s)",
                    ss["filename"],
                    int(ss["max_count"]),
                    ss["timestamp"].strftime("%Y-%m-%d %H:%M:%S JST"),
                )
            else:
                # ファイル削除
                if file_path.exists():
                    file_path.unlink()
                    logging.info("削除: %s", file_path)
                else:
                    logging.warning("ファイルなし: %s", file_path)

                # DBレコード削除
                cache_db.execute(
                    "DELETE FROM screenshot_metadata WHERE filename = ?",
                    (ss["filename"],),
                )

            deleted_count += 1

        if not dry_run:
            cache_db.commit()

    # 空ディレクトリを削除
    if deleted_count > 0:
        removed_dirs = remove_empty_directories(screenshot_dir, dry_run=dry_run)
        if removed_dirs > 0:
            if dry_run:
                logging.info("[dry-run] 空ディレクトリ削除対象: %d件", removed_dirs)
            else:
                logging.info("空ディレクトリ削除: %d件", removed_dirs)

    return deleted_count


def run_cleaner(
    config: dict,
    *,
    dry_run: bool = False,
    min_max_count: float = DEFAULT_MIN_MAX_COUNT,
    time_window_minutes: int = DEFAULT_TIME_WINDOW_MINUTES,
    min_magnitude: float = DEFAULT_MIN_MAGNITUDE,
) -> int:
    """
    クリーナーを実行する.

    Args:
        config: アプリケーション設定
        dry_run: True の場合、実際には削除しない
        min_max_count: 最小振幅閾値
        time_window_minutes: 地震との時間差（分）
        min_magnitude: 最小マグニチュード

    Returns:
        削除した件数

    """
    logging.info("クリーナー開始")
    logging.info(
        "条件: 振幅 >= %d, 時間窓 ±%d分, マグニチュード >= %.1f",
        int(min_max_count),
        time_window_minutes,
        min_magnitude,
    )

    # 削除対象を取得
    to_delete = get_screenshots_to_clean(
        config,
        min_max_count=min_max_count,
        time_window_minutes=time_window_minutes,
        min_magnitude=min_magnitude,
    )

    if not to_delete:
        logging.info("削除対象なし")
        return 0

    logging.info("削除対象: %d件", len(to_delete))

    # 削除実行
    deleted_count = delete_screenshots(config, to_delete, dry_run=dry_run)

    if dry_run:
        logging.info("[dry-run] 削除対象: %d件（実際には削除されていません）", deleted_count)
    else:
        logging.info("削除完了: %d件", deleted_count)

    return deleted_count


######################################################################
if __name__ == "__main__":
    import docopt

    assert __doc__ is not None  # noqa: S101 - type narrowing for pyright
    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    dry_run = args["-n"]
    debug_mode = args["-D"]
    min_max_count = int(args["--min-count"])
    time_window_minutes = int(args["--time-window"])
    min_magnitude = float(args["--min-mag"])

    my_lib.logger.init("cleaner", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file, pathlib.Path(SCHEMA_CONFIG))

    run_cleaner(
        config,
        dry_run=dry_run,
        min_max_count=min_max_count,
        time_window_minutes=time_window_minutes,
        min_magnitude=min_magnitude,
    )
