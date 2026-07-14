#!/usr/bin/env python3
"""
rsudp の Liveness チェックを行います

Usage:
  rsudp-healthz [-c CONFIG] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -D                : デバッグモードで動作します。
"""

import collections
import logging
import pathlib

import my_lib.config
import my_lib.healthz
import my_lib.healthz.cli
import my_lib.notify.slack

import rsudp.config

_LIVENESS_FILE = pathlib.Path("/dev/shm/rsudp.liveness")  # noqa: S108
_RSUDP_LOG_FILE = pathlib.Path("/tmp/rsudp/rsudp.log")  # noqa: S108
_LIVENESS_INTERVAL = 60
_CONTAINER_STARTUP_GRACE_PERIOD = 60  # コンテナ起動後の猶予期間（秒）
_LOG_TAIL_LINES = 50  # エラー通知に含めるログの行数


def _make_target() -> my_lib.healthz.HealthzTarget:
    # NOTE: テストが _LIVENESS_FILE をパッチできるよう、呼び出し時に参照する
    return my_lib.healthz.HealthzTarget(
        name="rsudp",
        liveness_file=_LIVENESS_FILE,
        interval=_LIVENESS_INTERVAL,
    )


def _check_liveness() -> float | None:
    """rsudp の liveness をチェックする."""
    return my_lib.healthz.check_liveness_elapsed(_make_target())


def _get_recent_logs(lines: int = _LOG_TAIL_LINES) -> str:
    """
    rsudp のログファイルから最新の指定行数を取得する.

    Args:
        lines: 取得する行数

    Returns:
        ログの内容。ファイルが存在しない場合は空文字列。

    """
    if not _RSUDP_LOG_FILE.exists():
        return "(log file not found)"

    try:
        with _RSUDP_LOG_FILE.open(encoding="utf-8", errors="replace") as f:
            recent_lines = collections.deque(f, maxlen=lines)
            return "".join(recent_lines)
    except Exception:
        logging.exception("Failed to read log file")
        return "(failed to read log file)"


def _notify_error(config: rsudp.config.Config, message: str) -> None:
    """Slack でエラー通知を送信する."""
    # ログの最新部分を取得してメッセージに追加
    recent_logs = _get_recent_logs()
    full_message = f"{message}\n\n*Recent logs:*\n```\n{recent_logs}\n```"

    my_lib.notify.slack.error(
        config.slack,
        "rsudp Liveness Check Failed",
        full_message,
    )


def _load_config(config_file, args):
    config_dict = my_lib.config.load(config_file)
    # NOTE: base_dir は絶対パスであることが要求される (相対 -c 指定でも動くよう resolve する)
    return rsudp.config.load_from_dict(config_dict, pathlib.Path(config_file).resolve().parent)


def _targets(config, args):
    return [_make_target()]


def _failure_handler(config, args, failed):
    """コンテナ起動後の猶予期間を過ぎている場合のみ Slack 通知する."""
    if my_lib.healthz.cli.within_startup_grace(_CONTAINER_STARTUP_GRACE_PERIOD):
        return

    # 通知メッセージ用に失敗理由 (経過秒) を取り直す
    elapsed = _check_liveness()
    if elapsed == -1:
        _notify_error(config, "Liveness file does not exist.")
    elif elapsed == -2:
        _notify_error(config, "Liveness file is corrupted (empty or unparseable).")
    elif elapsed is not None:
        _notify_error(config, f"Liveness file is stale. Last updated {elapsed:,.1f} seconds ago.")


SPEC = my_lib.healthz.cli.HealthzCliSpec(
    logger_name="rsudp.healthz",
    config_loader=_load_config,
    targets_builder=_targets,
    failure_handler=_failure_handler,
)


def main() -> None:
    """Console script entry point."""
    assert __doc__ is not None  # noqa: S101
    my_lib.healthz.cli.run(SPEC, __doc__)


if __name__ == "__main__":
    main()
