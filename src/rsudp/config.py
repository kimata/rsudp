"""アプリケーション設定の dataclass 定義"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Any

import my_lib.notify.slack
import my_lib.safe_access


@dataclass(frozen=True)
class ScreenshotConfig:
    """スクリーンショット設定"""

    path: pathlib.Path


@dataclass(frozen=True)
class PlotConfig:
    """プロット設定"""

    screenshot: ScreenshotConfig


@dataclass(frozen=True)
class DataConfig:
    """データパス設定"""

    cache: pathlib.Path
    quake: pathlib.Path
    selenium: pathlib.Path
    # miniSEED 波形アーカイブのディレクトリ（圧縮対象。未設定時は None）
    miniseed: pathlib.Path | None = None
    # 地震前後の区間のみを残す抽出（不可逆）を有効化するか
    miniseed_extract_quake: bool = False


@dataclass(frozen=True)
class WebappConfig:
    """Webアプリケーション設定"""

    static_dir_path: pathlib.Path


@dataclass(frozen=True)
class Config:
    """アプリケーション全体の設定"""

    plot: PlotConfig
    data: DataConfig
    webapp: WebappConfig
    slack: my_lib.notify.slack.SlackErrorOnlyConfig | my_lib.notify.slack.SlackEmptyConfig = field(
        default_factory=my_lib.notify.slack.SlackEmptyConfig
    )
    base_dir: pathlib.Path = field(default_factory=pathlib.Path.cwd)

    def __post_init__(self) -> None:
        # 全てのパスは絶対パスである invariant を保証する
        for label, path in (
            ("base_dir", self.base_dir),
            ("plot.screenshot.path", self.plot.screenshot.path),
            ("data.cache", self.data.cache),
            ("data.quake", self.data.quake),
            ("data.selenium", self.data.selenium),
            ("data.miniseed", self.data.miniseed),
            ("webapp.static_dir_path", self.webapp.static_dir_path),
        ):
            if path is None:
                continue
            if not path.is_absolute():
                msg = f"Config path must be absolute: {label}={path}"
                raise ValueError(msg)


def _parse_slack_config(
    slack_dict: dict[str, Any],
) -> my_lib.notify.slack.SlackErrorOnlyConfig | my_lib.notify.slack.SlackEmptyConfig:
    """
    Slack 設定をパースして SlackErrorOnlyConfig または SlackEmptyConfig を返す.
    """
    parsed = my_lib.notify.slack.SlackConfig.parse(slack_dict)

    # SlackErrorOnlyConfig または SlackEmptyConfig のみを許可
    if isinstance(parsed, my_lib.notify.slack.SlackErrorOnlyConfig | my_lib.notify.slack.SlackEmptyConfig):
        return parsed

    # その他の設定タイプの場合、SlackErrorOnlyConfig に変換を試みる
    # NOTE: SafeAccess を使用して属性の存在確認と値取得を簡略化
    sa = my_lib.safe_access.safe(parsed)
    if sa.error and sa.bot_token and sa.from_name:
        bot_token = sa.bot_token.value()
        from_name = sa.from_name.value()
        error = sa.error.value()
        if (
            isinstance(bot_token, str)
            and isinstance(from_name, str)
            and isinstance(error, my_lib.notify.slack.SlackErrorConfig)
        ):
            return my_lib.notify.slack.SlackErrorOnlyConfig(
                bot_token=bot_token,
                from_name=from_name,
                error=error,
            )

    # 変換できない場合は空設定を返す
    return my_lib.notify.slack.SlackEmptyConfig()


def _resolve_path(path_str: str, base_dir: pathlib.Path) -> pathlib.Path:
    """相対パスを base_dir から解決して絶対パスに変換する."""
    path = pathlib.Path(path_str)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def load_from_dict(config_dict: dict[str, Any], base_dir: pathlib.Path) -> Config:
    """辞書形式の設定を Config に変換する"""
    return Config(
        plot=PlotConfig(
            screenshot=ScreenshotConfig(
                path=_resolve_path(config_dict["plot"]["screenshot"]["path"], base_dir),
            ),
        ),
        data=DataConfig(
            cache=_resolve_path(config_dict["data"]["cache"], base_dir),
            quake=_resolve_path(config_dict["data"]["quake"], base_dir),
            selenium=_resolve_path(config_dict["data"]["selenium"], base_dir),
            miniseed=(
                _resolve_path(config_dict["data"]["miniseed"], base_dir)
                if config_dict["data"].get("miniseed")
                else None
            ),
            miniseed_extract_quake=bool(config_dict["data"].get("miniseed_extract_quake", False)),
        ),
        webapp=WebappConfig(
            static_dir_path=_resolve_path(config_dict["webapp"]["static_dir_path"], base_dir),
        ),
        slack=_parse_slack_config(config_dict.get("slack", {})),
        base_dir=base_dir,
    )
