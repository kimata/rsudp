#!/usr/bin/env python3
# ruff: noqa: S101
"""
healthz.py のテスト
"""

import time
import unittest.mock

from rsudp.cli import healthz


class TestGetRecentLogs:
    """_get_recent_logs のテスト"""

    def test_log_file_not_exists(self, temp_dir):
        """ログファイルが存在しない場合"""
        with unittest.mock.patch.object(healthz, "_RSUDP_LOG_FILE", temp_dir / "nonexistent.log"):
            result = healthz._get_recent_logs()
            assert result == "(log file not found)"

    def test_log_file_exists(self, temp_dir):
        """ログファイルが存在する場合"""
        log_file = temp_dir / "test.log"
        log_file.write_text("line1\nline2\nline3\n")

        with unittest.mock.patch.object(healthz, "_RSUDP_LOG_FILE", log_file):
            result = healthz._get_recent_logs(lines=2)
            assert "line2" in result
            assert "line3" in result

    def test_log_file_read_error(self, temp_dir):
        """ログファイルの読み取りエラー"""
        log_file = temp_dir / "test.log"
        log_file.write_text("content")

        with (
            unittest.mock.patch.object(healthz, "_RSUDP_LOG_FILE", log_file),
            unittest.mock.patch("pathlib.Path.open", side_effect=PermissionError("Permission denied")),
        ):
            result = healthz._get_recent_logs()
            assert result == "(failed to read log file)"


class TestCheckLiveness:
    """_check_liveness のテスト"""

    def test_liveness_file_not_exists(self, temp_dir):
        """Liveness ファイルが存在しない場合"""
        with unittest.mock.patch.object(healthz, "_LIVENESS_FILE", temp_dir / "nonexistent"):
            result = healthz._check_liveness()
            assert result == -1

    def test_liveness_file_fresh(self, temp_dir):
        """Liveness ファイルが新しい場合"""
        liveness_file = temp_dir / "liveness"
        liveness_file.touch()

        with unittest.mock.patch.object(healthz, "_LIVENESS_FILE", liveness_file):
            result = healthz._check_liveness()
            assert result is None

    def test_liveness_file_stale(self, temp_dir):
        """Liveness ファイルが古い場合"""
        import os

        liveness_file = temp_dir / "liveness"
        liveness_file.touch()

        # 3分前のタイムスタンプに設定
        old_time = time.time() - 180
        os.utime(liveness_file, (old_time, old_time))

        with unittest.mock.patch.object(healthz, "_LIVENESS_FILE", liveness_file):
            result = healthz._check_liveness()
            assert result is not None
            assert result > 120  # 2分以上経過


class TestNotifyError:
    """_notify_error のテスト"""

    def test_notify_error_sends_slack(self, config):
        """Slack にエラー通知を送信する"""
        with (
            unittest.mock.patch.object(healthz, "_get_recent_logs", return_value="test logs"),
            unittest.mock.patch("my_lib.notify.slack.error") as mock_slack,
        ):
            healthz._notify_error(config, "Test error message")

            mock_slack.assert_called_once()
            args = mock_slack.call_args
            assert "Test error message" in args[0][2]
            assert "test logs" in args[0][2]
