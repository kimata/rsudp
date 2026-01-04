#!/usr/bin/env python3
"""
rsudp の Liveness チェックを行います

Usage:
  healthz.py [-c CONFIG] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -D                : デバッグモードで動作します。
"""

import logging
import pathlib
import sys
import time

import my_lib.container_util
import my_lib.notify.slack

import rsudp.config

LIVENESS_FILE = pathlib.Path("/dev/shm/rsudp.liveness")  # noqa: S108
RSUDP_LOG_FILE = pathlib.Path("/tmp/rsudp/rsudp.log")  # noqa: S108
LIVENESS_INTERVAL = 60
CONTAINER_STARTUP_GRACE_PERIOD = 60  # コンテナ起動後の猶予期間（秒）
LOG_TAIL_LINES = 50  # エラー通知に含めるログの行数


def get_recent_logs(lines: int = LOG_TAIL_LINES) -> str:
    """
    rsudp のログファイルから最新の指定行数を取得する.

    Args:
        lines: 取得する行数

    Returns:
        ログの内容。ファイルが存在しない場合は空文字列。

    """
    if not RSUDP_LOG_FILE.exists():
        return "(log file not found)"

    try:
        with RSUDP_LOG_FILE.open(encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return "".join(recent_lines)
    except Exception:
        logging.exception("Failed to read log file")
        return "(failed to read log file)"


def check_liveness() -> bool:
    """
    rsudp の liveness をチェックする.

    rsudp の liveness ファイルは os.utime() で mtime を更新するため、
    ファイルの mtime を直接確認する。
    """
    if not LIVENESS_FILE.exists():
        logging.warning("rsudp is not executed.")
        return False

    mtime = LIVENESS_FILE.stat().st_mtime
    elapsed = time.time() - mtime

    # NOTE: 少なくとも1分は様子を見る
    if elapsed > max(LIVENESS_INTERVAL * 2, 60):
        logging.warning("Execution interval of rsudp is too long. (%s sec)", f"{elapsed:,.1f}")
        return False

    logging.debug("Execution interval of rsudp: %s sec", f"{elapsed:,.1f}")
    return True


def notify_error(config: rsudp.config.Config, message: str) -> None:
    """Slack でエラー通知を送信する."""
    # ログの最新部分を取得してメッセージに追加
    recent_logs = get_recent_logs()
    full_message = f"{message}\n\n*Recent logs:*\n```\n{recent_logs}\n```"

    my_lib.notify.slack.error(
        config.slack,
        "rsudp Liveness Check Failed",
        full_message,
    )


if __name__ == "__main__":
    import docopt
    import my_lib.config
    import my_lib.logger

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    debug_mode = args["-D"]

    my_lib.logger.init("rsudp.healthz", level=logging.DEBUG if debug_mode else logging.INFO)

    config_dict = my_lib.config.load(config_file)
    config = rsudp.config.load_from_dict(config_dict, pathlib.Path(config_file).parent)

    if check_liveness():
        logging.info("OK.")
        sys.exit(0)
    else:
        # コンテナ起動後の猶予期間を過ぎている場合のみ通知
        uptime = my_lib.container_util.get_uptime()
        if uptime > CONTAINER_STARTUP_GRACE_PERIOD:
            if not LIVENESS_FILE.exists():
                notify_error(config, "Liveness file does not exist.")
            else:
                mtime = LIVENESS_FILE.stat().st_mtime
                elapsed = time.time() - mtime
                notify_error(config, f"Liveness file is stale. Last updated {elapsed:.1f} seconds ago.")
        else:
            logging.info("Within startup grace period (%.1f sec), skipping notification.", uptime)

        sys.exit(1)
