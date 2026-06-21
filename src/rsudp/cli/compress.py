#!/usr/bin/env python3
"""
data ディレクトリを圧縮してディスク使用量を削減します.

miniSEED 波形アーカイブを zstd 圧縮し、スクリーンショット PNG を WebP へ変換します。
既存データの一括移行に使用します（継続的な圧縮はバックグラウンド監視が実行します）。

Usage:
  rsudp-compress [-c CONFIG] [-n] [-D] [--miniseed-only | --screenshots-only] [--extract-quake]

Options:
  -c CONFIG               : 設定ファイルを指定します。[default: config.yaml]
  -n                      : dry-run モード。実際には圧縮せず、対象を表示します。
  -D                      : デバッグモードで動作します。
  --miniseed-only         : miniSEED の処理のみ実行します。
  --screenshots-only      : スクリーンショットの変換のみ実行します。
  --extract-quake         : miniSEED から地震前後の区間のみを抽出します（不可逆）。
"""

import logging
import pathlib

import my_lib.config
import my_lib.logger

import rsudp.compress
import rsudp.config

_SCHEMA_CONFIG = "schema/config.schema"


def _log_result(label: str, result: rsudp.compress.CompressResult, *, dry_run: bool) -> None:
    """圧縮結果をログ出力する."""
    prefix = "[dry-run] " if dry_run else ""
    if dry_run:
        logging.info(
            "%s%s: 対象 %d件, 削除 %d件, 推定削減元サイズ %.1f MB",
            prefix,
            label,
            result.processed,
            result.deleted,
            result.bytes_before / 1024 / 1024,
        )
    else:
        logging.info(
            "%s%s: 処理 %d件, 削除 %d件, スキップ %d件, 削減 %.1f MB (%.1f -> %.1f MB)",
            prefix,
            label,
            result.processed,
            result.deleted,
            result.skipped,
            result.saved / 1024 / 1024,
            result.bytes_before / 1024 / 1024,
            result.bytes_after / 1024 / 1024,
        )


def _run_compress(
    config: rsudp.config.Config,
    *,
    dry_run: bool = False,
    miniseed_only: bool = False,
    screenshots_only: bool = False,
    extract_quake: bool = False,
) -> None:
    """圧縮を実行する."""
    logging.info("圧縮開始 (dry_run=%s)", dry_run)

    if not screenshots_only:
        if config.data.miniseed is None:
            logging.warning("data.miniseed が設定されていないため miniSEED 処理をスキップします")
        else:
            result = rsudp.compress.compress_miniseed(config.data.miniseed, dry_run=dry_run)
            _log_result("miniSEED", result, dry_run=dry_run)
            if extract_quake:
                result = rsudp.compress.extract_earthquake_miniseed(
                    config.data.miniseed, config.data.quake, dry_run=dry_run
                )
                _log_result("地震区間抽出", result, dry_run=dry_run)

    if not miniseed_only:
        result = rsudp.compress.convert_screenshots(
            config.plot.screenshot.path, config.data.cache, dry_run=dry_run
        )
        _log_result("スクリーンショット", result, dry_run=dry_run)

    logging.info("圧縮完了")


def main() -> None:
    """Console script entry point."""
    import docopt

    assert __doc__ is not None  # noqa: S101 - type narrowing for pyright
    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    dry_run = args["-n"]
    debug_mode = args["-D"]
    miniseed_only = args["--miniseed-only"]
    screenshots_only = args["--screenshots-only"]
    extract_quake = args["--extract-quake"]

    my_lib.logger.init("compress", level=logging.DEBUG if debug_mode else logging.INFO)

    config_dict = my_lib.config.load(config_file, pathlib.Path(_SCHEMA_CONFIG))
    config = rsudp.config.load_from_dict(config_dict, pathlib.Path.cwd())

    _run_compress(
        config,
        dry_run=dry_run,
        miniseed_only=miniseed_only,
        screenshots_only=screenshots_only,
        extract_quake=extract_quake,
    )


if __name__ == "__main__":
    main()
