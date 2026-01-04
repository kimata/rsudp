#!/usr/bin/env python3
"""
rsudp の Liveness チェックを行います

Usage:
  healthz.py [-D]

Options:
  -D                : デバッグモードで動作します。
"""

import logging
import pathlib
import sys
import time

LIVENESS_FILE = pathlib.Path("/dev/shm/rsudp.liveness")  # noqa: S108
LIVENESS_INTERVAL = 60


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


if __name__ == "__main__":
    import docopt
    import my_lib.logger

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)

    debug_mode = args["-D"]

    my_lib.logger.init("rsudp.healthz", level=logging.DEBUG if debug_mode else logging.INFO)

    if check_liveness():
        logging.info("OK.")
        sys.exit(0)
    else:
        sys.exit(1)
