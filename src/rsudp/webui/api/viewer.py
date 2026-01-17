"""Screenshot viewer API endpoints for rsudp web interface."""

import dataclasses
import datetime
import functools
import html
import threading
import traceback
from pathlib import Path

import flask
import my_lib.flask_util
import my_lib.webapp.config

import rsudp.config
import rsudp.quake.crawl
import rsudp.quake.database
import rsudp.screenshot_manager
import rsudp.types

viewer_api = flask.Blueprint("viewer_api", __name__, url_prefix="/rsudp")
blueprint = viewer_api  # Alias for compatibility with webui.py


def no_cache(func):
    """動的 API レスポンスにキャッシュ無効化ヘッダーを追加するデコレータ."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        response = func(*args, **kwargs)
        # jsonify の結果は Response オブジェクトまたはタプル
        if isinstance(response, tuple):
            # エラーレスポンス (response, status_code) の場合
            resp = flask.make_response(response[0])
            resp.status_code = response[1]
        else:
            resp = flask.make_response(response)
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

    return wrapper


# Global instance of ScreenshotManager
_screenshot_manager: rsudp.screenshot_manager.ScreenshotManager | None = None

# Lock for scan operation to prevent concurrent scans
_scan_lock = threading.Lock()
_is_scanning = False


def _get_config() -> rsudp.config.Config:
    """Get Config instance from Flask app."""
    return flask.current_app.config["CONFIG"]


def _get_screenshot_manager() -> rsudp.screenshot_manager.ScreenshotManager:
    """Get or create ScreenshotManager instance."""
    global _screenshot_manager
    if _screenshot_manager is None:
        config = _get_config()
        _screenshot_manager = rsudp.screenshot_manager.ScreenshotManager(config)
        # Initialize: organize files and scan cache once at startup
        _screenshot_manager.organize_files()
        _screenshot_manager.scan_and_cache_all()
    return _screenshot_manager


def _resolve_config_path(path: Path) -> Path:
    """設定から取得したパスを解決する（相対パスの場合はプロジェクトルートから解決）."""
    if path.is_absolute():
        return path
    # srcディレクトリの親ディレクトリ（プロジェクトルート）を基準にする
    project_root = Path.cwd().parent if Path.cwd().name == "src" else Path.cwd()
    return project_root / path


def _get_screenshots_path() -> Path:
    """Get the screenshots directory path from config."""
    config = _get_config()
    return _resolve_config_path(config.plot.screenshot.path)


def _get_quake_db_path() -> Path | None:
    """Get the quake database path from config."""
    config = _get_config()
    return _resolve_config_path(config.data.quake)


def _format_screenshot_with_earthquake(s: dict, quake_db_path: Path | None = None) -> dict:
    """Format screenshot dict with optional earthquake info."""
    manager = _get_screenshot_manager()

    # 地震情報を取得（辞書に含まれていない場合）
    earthquake = None
    if "earthquake" in s and s["earthquake"] is not None:
        earthquake = s["earthquake"]
    elif quake_db_path:
        earthquake = manager.get_earthquake_for_screenshot(s["timestamp"], quake_db_path)

    return rsudp.types.screenshot_dict_to_response(s, earthquake)


@viewer_api.route("/api/screenshot/", methods=["GET"])
@my_lib.flask_util.gzipped
@no_cache
def list_screenshots():
    """
    List all screenshot files with parsed metadata.

    Returns files sorted by timestamp (newest first).
    Query parameters:
    - min_max_signal: Minimum maximum signal value to filter screenshots
    - earthquake_only: If true, only return screenshots during earthquake windows
    """
    try:
        manager = _get_screenshot_manager()

        # Get filter parameters
        min_max_signal = flask.request.args.get("min_max_signal", type=float)
        earthquake_only = flask.request.args.get("earthquake_only", "false").lower() == "true"

        quake_db_path = _get_quake_db_path()

        if earthquake_only and quake_db_path and quake_db_path.exists():
            # 事前計算された地震関連付けを使って高速にフィルタリング
            screenshots = manager.get_screenshots_with_earthquake_filter_fast(
                quake_db_path=quake_db_path,
                min_max_signal=min_max_signal,
            )
            # すでに earthquake キーが含まれているのでそのまま使用
            formatted_screenshots = [_format_screenshot_with_earthquake(s, None) for s in screenshots]
        else:
            # Get screenshots with optional maximum signal filter
            # 地震情報の付加は行わない（パフォーマンス向上のため）
            screenshots = manager.get_screenshots_with_signal_filter(min_max_signal)
            formatted_screenshots = [_format_screenshot_with_earthquake(s, None) for s in screenshots]

        return flask.jsonify(
            {
                "screenshots": formatted_screenshots,
                "total": len(formatted_screenshots),
                "path": str(_get_screenshots_path()),
            }
        )

    except Exception as e:
        return flask.jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@viewer_api.route("/api/screenshot/years/", methods=["GET"])
@no_cache
def list_years():
    """
    Get list of available years.

    Query parameters:
    - min_max_signal: Minimum maximum signal value to filter years
    """
    try:
        manager = _get_screenshot_manager()
        min_max_signal = flask.request.args.get("min_max_signal", type=float)

        # Get available dates with maximum signal filter
        dates = manager.get_available_dates(min_max_signal)

        # Extract unique years
        years = sorted({d.year for d in dates}, reverse=True)

        return flask.jsonify({"years": years})

    except Exception as e:
        return flask.jsonify({"error": str(e)}), 500


@viewer_api.route("/api/screenshot/<int:year>/months/", methods=["GET"])
@no_cache
def list_months(year: int):
    """
    Get list of available months for a specific year.

    Query parameters:
    - min_max_signal: Minimum maximum signal value to filter months
    """
    try:
        manager = _get_screenshot_manager()
        min_max_signal = flask.request.args.get("min_max_signal", type=float)

        # Get available dates with maximum signal filter
        dates = manager.get_available_dates(min_max_signal)

        # Extract months for the specified year
        months = sorted({d.month for d in dates if d.year == year}, reverse=True)

        return flask.jsonify({"months": months})

    except Exception as e:
        return flask.jsonify({"error": str(e)}), 500


@viewer_api.route("/api/screenshot/<int:year>/<int:month>/days/", methods=["GET"])
@no_cache
def list_days(year: int, month: int):
    """
    Get list of available days for a specific year and month.

    Query parameters:
    - min_max_signal: Minimum maximum signal value to filter days
    """
    try:
        manager = _get_screenshot_manager()
        min_max_signal = flask.request.args.get("min_max_signal", type=float)

        # Get available dates with maximum signal filter
        dates = manager.get_available_dates(min_max_signal)

        # Extract days for the specified year and month
        days = sorted({d.day for d in dates if d.year == year and d.month == month}, reverse=True)

        return flask.jsonify({"days": days})

    except Exception as e:
        return flask.jsonify({"error": str(e)}), 500


@viewer_api.route("/api/screenshot/<int:year>/<int:month>/<int:day>/", methods=["GET"])
@my_lib.flask_util.gzipped
@no_cache
def list_by_date(year: int, month: int, day: int):
    """
    Get screenshots for a specific date.

    Query parameters:
    - min_max_signal: Minimum maximum signal value to filter screenshots
    """
    try:
        manager = _get_screenshot_manager()
        min_max_signal = flask.request.args.get("min_max_signal", type=float)

        # Get screenshots with optional maximum signal filter
        screenshots = manager.get_screenshots_with_signal_filter(min_max_signal)

        # Filter by date and format
        files = [
            rsudp.types.screenshot_dict_to_response(s)
            for s in screenshots
            if s["year"] == year and s["month"] == month and s["day"] == day
        ]

        return flask.jsonify({"screenshots": files, "total": len(files)})

    except Exception as e:
        return flask.jsonify({"error": str(e)}), 500


def _get_image_file_path(filename: str):
    """Get the actual file path for a given filename."""
    screenshots_dir = _get_screenshots_path()

    # First try direct path
    file_path = screenshots_dir / filename

    # If not found, try searching in date-based subdirectories
    if not file_path.exists():
        # Search recursively for the filename
        for found_path in screenshots_dir.rglob(filename):
            if found_path.is_file():
                file_path = found_path
                break

    return str(file_path) if file_path.exists() else None


@viewer_api.route("/api/screenshot/image/<path:filename>", methods=["GET"])
@my_lib.flask_util.file_etag(
    filename_func=lambda filename: _get_image_file_path(filename),
    cache_control="public, max-age=31536000, immutable",
)
def get_image(filename: str):
    """Serve a specific screenshot image with ETag caching."""
    try:
        file_path_str = _get_image_file_path(filename)

        if not file_path_str:
            return flask.jsonify({"error": "File not found"}), 404

        file_path = Path(file_path_str)

        if file_path.stat().st_size == 0:
            return flask.jsonify({"error": "File is empty"}), 404

        # Send file with optimal cache headers
        return flask.send_file(
            str(file_path),
            mimetype="image/png",
            as_attachment=False,
            download_name=None,
            # Disable Flask's built-in conditional requests since we're using ETag
            conditional=False,
            # Set max age to 1 year since screenshots are immutable
            max_age=31536000,  # 1 year in seconds
        )

    except Exception as e:
        return flask.jsonify({"error": str(e)}), 500


@viewer_api.route("/api/screenshot/ogp/<path:filename>", methods=["GET"])
def get_ogp_image(filename: str):
    """
    OGP用に最適化された画像を返す.

    画像の上部を切り出し、Twitter Cards推奨の1.91:1アスペクト比にクロップする。
    """
    import io

    import PIL.Image

    try:
        file_path_str = _get_image_file_path(filename)

        if not file_path_str:
            return flask.jsonify({"error": "File not found"}), 404

        file_path = Path(file_path_str)

        if file_path.stat().st_size == 0:
            return flask.jsonify({"error": "File is empty"}), 404

        # 画像を開く
        with PIL.Image.open(file_path) as img:
            width, height = img.size

            # Twitter Cards推奨アスペクト比 1.91:1
            target_ratio = 1.91
            target_height = int(width / target_ratio)

            # 画像の上部から切り出し（波形の冒頭を表示）
            cropped = img.crop((0, 0, width, target_height)) if target_height < height else img

            # PNGとして出力
            output = io.BytesIO()
            cropped.save(output, format="PNG", optimize=True)
            output.seek(0)

            response = flask.send_file(
                output,
                mimetype="image/png",
                as_attachment=False,
                download_name=None,
            )

            # キャッシュヘッダーを設定
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"

            return response

    except Exception as e:
        return flask.jsonify({"error": str(e)}), 500


@viewer_api.route("/api/screenshot/latest/", methods=["GET"])
@no_cache
def get_latest():
    """
    Get the most recent screenshot.

    Query parameters:
    - min_max_signal: Minimum maximum signal value to filter screenshots
    """
    try:
        manager = _get_screenshot_manager()
        min_max_signal = flask.request.args.get("min_max_signal", type=float)

        # Get screenshots with optional maximum signal filter
        screenshots = manager.get_screenshots_with_signal_filter(min_max_signal)

        if not screenshots:
            return flask.jsonify({"error": "No screenshots found"}), 404

        # First one is already the latest (sorted by timestamp desc)
        latest = screenshots[0]

        return flask.jsonify(rsudp.types.screenshot_dict_to_response(latest))

    except Exception as e:
        return flask.jsonify({"error": str(e)}), 500


@viewer_api.route("/api/screenshot/statistics/", methods=["GET"])
@no_cache
def get_statistics():
    """
    Get signal value statistics for screenshots.

    Query parameters:
    - earthquake_only: If true, only include screenshots during earthquake windows
    """
    try:
        manager = _get_screenshot_manager()
        quake_db_path = _get_quake_db_path()
        earthquake_only = flask.request.args.get("earthquake_only", "false").lower() == "true"

        stats = manager.get_signal_statistics(
            quake_db_path=quake_db_path,
            earthquake_only=earthquake_only,
        )

        # Add absolute total (without earthquake filter)
        if earthquake_only:
            all_stats = manager.get_signal_statistics(
                quake_db_path=quake_db_path,
                earthquake_only=False,
            )
            stats.absolute_total = all_stats.total
        else:
            stats.absolute_total = stats.total

        # Add earthquake count
        if quake_db_path and quake_db_path.exists():
            quake_db = rsudp.quake.database.QuakeDatabase(_get_config())
            stats.earthquake_count = quake_db.count_earthquakes()
        else:
            stats.earthquake_count = 0

        return flask.jsonify(dataclasses.asdict(stats))
    except Exception as e:
        return flask.jsonify({"error": str(e)}), 500


@viewer_api.route("/api/screenshot/scan/", methods=["POST"])
@no_cache
def scan_screenshots():
    """
    Scan for new screenshot files and update cache.

    Uses a lock to prevent concurrent scans. If a scan is already in progress,
    returns immediately with a message indicating that.
    """
    global _is_scanning

    # Try to acquire lock without blocking
    if not _scan_lock.acquire(blocking=False):
        return flask.jsonify({"success": True, "message": "Scan already in progress", "skipped": True})

    try:
        if _is_scanning:
            return flask.jsonify({"success": True, "message": "Scan already in progress", "skipped": True})

        _is_scanning = True
        manager = _get_screenshot_manager()

        # Organize files and scan for new ones
        manager.organize_files()
        new_count = manager.scan_and_cache_all()

        return flask.jsonify({"success": True, "new_files": new_count, "skipped": False})
    except Exception as e:
        return flask.jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500
    finally:
        _is_scanning = False
        _scan_lock.release()


@viewer_api.route("/api/earthquake/crawl/", methods=["POST"])
@no_cache
def crawl_earthquake_data():
    """Trigger earthquake data crawl from JMA."""
    try:
        config = _get_config()
        new_count = rsudp.quake.crawl.crawl_earthquakes(config, min_intensity=3)
        return flask.jsonify({"success": True, "new_earthquakes": new_count})
    except Exception as e:
        return flask.jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@viewer_api.route("/api/earthquake/list/", methods=["GET"])
@my_lib.flask_util.gzipped
@no_cache
def list_earthquakes():
    """List all stored earthquakes."""
    try:
        config = _get_config()
        quake_db = rsudp.quake.database.QuakeDatabase(config)
        earthquakes = quake_db.get_all_earthquakes(limit=100)
        earthquakes_dict = [dataclasses.asdict(eq) for eq in earthquakes]
        return flask.jsonify({"earthquakes": earthquakes_dict, "total": len(earthquakes_dict)})
    except Exception as e:
        return flask.jsonify({"error": str(e)}), 500


@viewer_api.route("/api/screenshot/clean/", methods=["POST"])
@no_cache
def clean_screenshots():
    """
    地震に関連しない高振幅スクリーンショットを削除する.

    Request body (JSON):
    - min_max_count: 最小振幅閾値 (default: 300000)
    - time_window_minutes: 地震との時間窓（分）(default: 10)
    - min_magnitude: 最小マグニチュード (default: 3.0)
    - dry_run: True の場合、実際には削除しない (default: False)
    """
    try:
        import rsudp.cli.cleaner

        config = _get_config()

        # リクエストパラメータを取得
        data = flask.request.get_json() or {}
        min_max_count = data.get("min_max_count", rsudp.cli.cleaner.DEFAULT_MIN_MAX_COUNT)
        time_window_minutes = data.get("time_window_minutes", rsudp.cli.cleaner.DEFAULT_TIME_WINDOW_MINUTES)
        min_magnitude = data.get("min_magnitude", rsudp.cli.cleaner.DEFAULT_MIN_MAGNITUDE)
        dry_run = data.get("dry_run", False)

        # 削除対象を取得
        to_delete = rsudp.cli.cleaner.get_screenshots_to_clean(
            config,
            min_max_count=min_max_count,
            time_window_minutes=time_window_minutes,
            min_magnitude=min_magnitude,
        )

        if dry_run:
            # dry-run モードでは削除対象のリストを返すだけ
            return flask.jsonify(
                {
                    "success": True,
                    "dry_run": True,
                    "to_delete_count": len(to_delete),
                    "to_delete": [
                        {
                            "filename": ss["filename"],
                            "max_count": ss["max_count"],
                            "timestamp": ss["timestamp"].isoformat(),
                        }
                        for ss in to_delete
                    ],
                }
            )

        # 実際に削除
        deleted_count = rsudp.cli.cleaner.delete_screenshots(config, to_delete, dry_run=False)

        return flask.jsonify(
            {
                "success": True,
                "dry_run": False,
                "deleted_count": deleted_count,
            }
        )

    except Exception as e:
        return flask.jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


def _get_ogp_content_for_screenshot(
    filename: str,
    base_url: str,
) -> tuple[str, str, str, str]:
    """スクリーンショットのOGPコンテンツを取得する."""
    manager = _get_screenshot_manager()
    quake_db_path = _get_quake_db_path()

    # ファイル名からタイムスタンプを解析
    parsed = rsudp.types.parse_filename(filename)
    if not parsed:
        return ("", "", "", "")

    # スクリーンショットのメタデータを取得
    screenshots = manager.get_screenshots_with_signal_filter(None)
    screenshot = next((s for s in screenshots if s["filename"] == filename), None)
    if not screenshot:
        return ("", "", "", "")

    # 日時をフォーマット（JSTに変換）
    ts = datetime.datetime.fromisoformat(screenshot["timestamp"])
    jst = ts.astimezone(rsudp.types.JST)
    date_str = jst.strftime("%-m/%-d %H:%M")

    # 地震情報を取得
    earthquake = (
        manager.get_earthquake_for_screenshot(screenshot["timestamp"], quake_db_path)
        if quake_db_path
        else None
    )

    if earthquake:
        eq_ts = datetime.datetime.fromisoformat(earthquake.detected_at)
        eq_date_str = eq_ts.strftime("%-m/%-d %H:%M")
        title = f"{eq_date_str} {earthquake.epicenter_name} M{earthquake.magnitude}"
        description = (
            f"震度{earthquake.max_intensity} | 深さ{earthquake.depth}km | Raspberry Shake 地震計記録"
        )
    else:
        title = f"{date_str} 地震計記録"
        desc_parts = []
        if screenshot.get("max_count"):
            desc_parts.append(f"最大振幅: {int(screenshot['max_count']):,}")
        if screenshot.get("sta"):
            desc_parts.append(f"STA: {int(screenshot['sta']):,}")
        if screenshot.get("sta_lta_ratio"):
            desc_parts.append(f"比率: {screenshot['sta_lta_ratio']:.3f}")
        description = " | ".join(desc_parts) if desc_parts else "Raspberry Shake 地震計のスクリーンショット"

    image_url = f"{base_url}/api/screenshot/ogp/{filename}"
    page_url = f"{base_url}/?file={filename}"

    return (title, description, image_url, page_url)


def _build_ogp_meta_tags(title: str, description: str, image_url: str, page_url: str) -> str:
    """OGPメタタグのHTML文字列を構築する."""
    # HTMLエスケープ
    title = html.escape(title)
    description = html.escape(description)
    image_url = html.escape(image_url)
    page_url = html.escape(page_url)

    meta_tags = f"""
    <!-- Open Graph / Facebook -->
    <meta property="og:type" content="website">
    <meta property="og:url" content="{page_url}">
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="{description}">
    <meta property="og:site_name" content="RSUDP スクリーンショットビューア">"""

    if image_url:
        meta_tags += f"""
    <meta property="og:image" content="{image_url}">
    <meta property="og:image:type" content="image/png">"""

    meta_tags += f"""

    <!-- Twitter -->
    <meta name="twitter:card" content="{"summary_large_image" if image_url else "summary"}">
    <meta name="twitter:url" content="{page_url}">
    <meta name="twitter:title" content="{title}">
    <meta name="twitter:description" content="{description}">"""

    if image_url:
        meta_tags += f"""
    <meta name="twitter:image" content="{image_url}">"""

    return meta_tags


def _generate_ogp_meta_tags(filename: str | None, base_url: str) -> str:
    """OGPメタタグを生成する."""
    # デフォルト値
    title = "RSUDP スクリーンショットビューア"
    description = "Raspberry Shake 地震計のスクリーンショットビューア"
    image_url = ""
    page_url = base_url

    if filename:
        try:
            content = _get_ogp_content_for_screenshot(filename, base_url)
            if content[0]:  # titleが取得できた場合
                title, description, image_url, page_url = content
        except Exception:  # noqa: S110
            pass  # エラー時はデフォルト値を使用

    return _build_ogp_meta_tags(title, description, image_url, page_url)


@viewer_api.route("/", methods=["GET"])
def index_with_ogp() -> flask.Response:
    """
    OGPメタタグを含むindex.htmlを返す.

    クエリパラメータ:
    - file: スクリーンショットのファイル名（OGP生成に使用）
    """
    try:
        # 静的ファイルディレクトリからindex.htmlを読み込む
        if my_lib.webapp.config.STATIC_DIR_PATH is None:
            return flask.Response("Static directory not configured", status=500)

        index_path = my_lib.webapp.config.STATIC_DIR_PATH / "index.html"
        if not index_path.exists():
            return flask.Response("index.html not found", status=404)

        # index.htmlを読み込む
        with index_path.open(encoding="utf-8") as f:
            html_content = f.read()

        # ベースURLを構築
        # X-Forwarded-Proto と X-Forwarded-Host を考慮
        scheme = flask.request.headers.get("X-Forwarded-Proto", flask.request.scheme)
        host = flask.request.headers.get("X-Forwarded-Host", flask.request.host)
        base_url = f"{scheme}://{host}/rsudp"

        # ファイル名を取得
        filename = flask.request.args.get("file")

        # OGPメタタグを生成
        ogp_tags = _generate_ogp_meta_tags(filename, base_url)

        # </head>の前にOGPタグを挿入
        html_content = html_content.replace("</head>", f"{ogp_tags}\n    </head>")

        return flask.Response(html_content, mimetype="text/html")

    except Exception as e:
        return flask.Response(f"Error: {e}\n{traceback.format_exc()}", status=500)
