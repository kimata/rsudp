# ruff: noqa: S101
"""
types モジュールのユニットテスト.

型定義と parse_filename 関数をテストします。
"""

from datetime import UTC, datetime

import rsudp.types


class TestParseFilename:
    """ファイル名解析のテスト."""

    def test_parse_valid_filename(self):
        """有効なファイル名が正しくパースされることを確認."""
        result = rsudp.types.parse_filename("SHAKE-2025-12-12-190542.png")

        assert result is not None
        assert result.prefix == "SHAKE"
        assert result.year == 2025
        assert result.month == 12
        assert result.day == 12
        assert result.hour == 19
        assert result.minute == 5
        assert result.second == 42
        assert "+00:00" in result.timestamp  # UTC

    def test_parse_alert_filename(self):
        """ALERT プレフィックスのファイル名が正しくパースされることを確認."""
        result = rsudp.types.parse_filename("ALERT-2025-08-14-091523.png")

        assert result is not None
        assert result.prefix == "ALERT"
        assert result.year == 2025
        assert result.month == 8
        assert result.day == 14

    def test_parse_invalid_filename_returns_none(self):
        """無効なファイル名で None が返されることを確認."""
        assert rsudp.types.parse_filename("invalid.png") is None
        assert rsudp.types.parse_filename("no-date.png") is None
        assert rsudp.types.parse_filename("SHAKE-2025-12-12.png") is None


class TestTimestampUTC:
    """タイムスタンプの UTC 処理テスト."""

    def test_filename_timestamp_is_utc(self):
        """ファイル名から抽出されたタイムスタンプが UTC であることを確認."""
        result = rsudp.types.parse_filename("SHAKE-2025-12-12-190542.png")

        assert result is not None

        # ISO フォーマットで UTC (+00:00) であることを確認
        assert result.timestamp == "2025-12-12T19:05:42+00:00"

        # datetime に変換して UTC であることを確認
        ts = datetime.fromisoformat(result.timestamp)
        assert ts.tzinfo == UTC


class TestJSTConstant:
    """JST 定数のテスト."""

    def test_jst_timezone(self):
        """JST タイムゾーンが正しく定義されていることを確認."""
        jst = rsudp.types.JST

        # UTC の時刻を JST に変換してオフセットを確認
        utc_time = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
        jst_time = utc_time.astimezone(jst)

        # UTC 0:00 は JST 9:00
        assert jst_time.hour == 9
