"""アプリケーション設定の dataclass 定義"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Any

import my_lib.notify.slack


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


def _parse_slack_config(
    slack_dict: dict[str, Any],
) -> my_lib.notify.slack.SlackErrorOnlyConfig | my_lib.notify.slack.SlackEmptyConfig:
    """
    Slack 設定をパースして SlackErrorOnlyConfig または SlackEmptyConfig を返す.
    """
    parsed = my_lib.notify.slack.parse_config(slack_dict)

    # SlackErrorOnlyConfig または SlackEmptyConfig のみを許可
    if isinstance(parsed, my_lib.notify.slack.SlackErrorOnlyConfig | my_lib.notify.slack.SlackEmptyConfig):
        return parsed

    # その他の設定タイプの場合、SlackErrorOnlyConfig に変換を試みる
    # NOTE: hasattr チェック後でも型が絞り込まれないため getattr を使用 (B009 を無視)
    if hasattr(parsed, "error") and hasattr(parsed, "bot_token") and hasattr(parsed, "from_name"):
        return my_lib.notify.slack.SlackErrorOnlyConfig(
            bot_token=getattr(parsed, "bot_token"),  # noqa: B009
            from_name=getattr(parsed, "from_name"),  # noqa: B009
            error=getattr(parsed, "error"),  # noqa: B009
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
        ),
        webapp=WebappConfig(
            static_dir_path=_resolve_path(config_dict["webapp"]["static_dir_path"], base_dir),
        ),
        slack=_parse_slack_config(config_dict.get("slack", {})),
        base_dir=base_dir,
    )
