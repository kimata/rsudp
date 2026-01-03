"""Screenshot viewer API endpoints for rsudp web interface."""

import re
import threading
from datetime import UTC, datetime
from pathlib import Path

import my_lib.flask_util
from flask import Blueprint, current_app, jsonify, request, send_file

from rsudp.quake.crawl import crawl_earthquakes
from rsudp.screenshot_manager import ScreenshotManager

viewer_api = Blueprint("viewer_api", __name__, url_prefix="/rsudp")
blueprint = viewer_api  # Alias for compatibility with webui.py

# Global instance of ScreenshotManager
_screenshot_manager: ScreenshotManager | None = None

# Lock for scan operation to prevent concurrent scans
_scan_lock = threading.Lock()
_is_scanning = False


def get_screenshot_manager() -> ScreenshotManager:
    """Get or create ScreenshotManager instance."""
    global _screenshot_manager  # noqa: PLW0603
    if _screenshot_manager is None:
        config = current_app.config["CONFIG"]
        # Ensure cache path is set
        if "data" not in config:
            config["data"] = {}
        if "cache" not in config["data"]:
            config["data"]["cache"] = "data/cache.db"
        _screenshot_manager = ScreenshotManager(config)
        # Initialize: organize files and scan cache once at startup
        _screenshot_manager.organize_files()
        _screenshot_manager.scan_and_cache_all()
    return _screenshot_manager


def parse_filename(filename: str) -> dict | None:
    """
    Parse screenshot filename to extract timestamp information.

    Format: PREFIX-YYYY-MM-DD-HHMMSS.png (e.g., SHAKE-2025-08-12-104039.png)
    """
    pattern = r"^(.+?)-(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})(\d{2})\.png$"
    match = re.match(pattern, filename)

    if not match:
        return None

    prefix, year, month, day, hour, minute, second = match.groups()

    return {
        "filename": filename,
        "prefix": prefix,
        "year": int(year),
        "month": int(month),
        "day": int(day),
        "hour": int(hour),
        "minute": int(minute),
        "second": int(second),
        "timestamp": datetime(
            int(year), int(month), int(day), int(hour), int(minute), int(second), tzinfo=UTC
        ).isoformat(),
    }


def get_screenshots_path() -> Path:
    """Get the screenshots directory path from config."""
    path = Path(current_app.config["CONFIG"]["plot"]["screenshot"]["path"])

    # 相対パスの場合は、プロジェクトルートから解決
    if not path.is_absolute():
        # srcディレクトリの親ディレクトリ（プロジェクトルート）を基準にする
        project_root = Path.cwd().parent if Path.cwd().name == "src" else Path.cwd()
        path = project_root / path

    return path


def get_quake_db_path() -> Path | None:
    """Get the quake database path from config."""
    quake_path = current_app.config["CONFIG"].get("data", {}).get("quake")
    if quake_path:
        path = Path(quake_path)
        if not path.is_absolute():
            project_root = Path.cwd().parent if Path.cwd().name == "src" else Path.cwd()
            path = project_root / path
        return path
    return None


def format_screenshot_with_earthquake(s: dict, quake_db_path: Path | None = None) -> dict:
    """Format screenshot dict with optional earthquake info."""
    manager = get_screenshot_manager()

    result = {
        "filename": s["filename"],
        "prefix": s["filename"].split("-")[0],
        "year": s["year"],
        "month": s["month"],
        "day": s["day"],
        "hour": s["hour"],
        "minute": s["minute"],
        "second": s["second"],
        "timestamp": s["timestamp"],
        "sta": s["sta"],
        "lta": s["lta"],
        "sta_lta_ratio": s["sta_lta_ratio"],
        "max_count": s["max_count"],
        "metadata": s["metadata"],
    }

    # Add earthquake info if available
    if "earthquake" in s:
        result["earthquake"] = s["earthquake"]
    elif quake_db_path:
        eq = manager.get_earthquake_for_screenshot(s["timestamp"], quake_db_path)
        if eq:
            result["earthquake"] = eq

    return result


@viewer_api.route("/api/screenshot/", methods=["GET"])
def list_screenshots():
    """
    List all screenshot files with parsed metadata.

    Returns files sorted by timestamp (newest first).
    Query parameters:
    - min_max_signal: Minimum maximum signal value to filter screenshots
    - earthquake_only: If true, only return screenshots during earthquake windows
    """
    try:
        manager = get_screenshot_manager()

        # Get filter parameters
        min_max_signal = request.args.get("min_max_signal", type=float)
        earthquake_only = request.args.get("earthquake_only", "false").lower() == "true"

        quake_db_path = get_quake_db_path()

        if earthquake_only and quake_db_path and quake_db_path.exists():
            # Get screenshots filtered by earthquake time windows
            screenshots = manager.get_screenshots_with_earthquake_filter(
                min_max_signal=min_max_signal,
                quake_db_path=quake_db_path,
            )
            formatted_screenshots = [format_screenshot_with_earthquake(s, quake_db_path) for s in screenshots]
        else:
            # Get screenshots with optional maximum signal filter
            screenshots = manager.get_screenshots_with_signal_filter(min_max_signal)
            formatted_screenshots = [format_screenshot_with_earthquake(s, quake_db_path) for s in screenshots]

        return jsonify(
            {
                "screenshots": formatted_screenshots,
                "total": len(formatted_screenshots),
                "path": str(get_screenshots_path()),
            }
        )

    except Exception as e:
        import traceback

        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@viewer_api.route("/api/screenshot/years/", methods=["GET"])
def list_years():
    """
    Get list of available years.

    Query parameters:
    - min_max_signal: Minimum maximum signal value to filter years
    """
    try:
        manager = get_screenshot_manager()
        min_max_signal = request.args.get("min_max_signal", type=float)

        # Get available dates with maximum signal filter
        dates = manager.get_available_dates(min_max_signal)

        # Extract unique years
        years = sorted({d["year"] for d in dates}, reverse=True)

        return jsonify({"years": years})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@viewer_api.route("/api/screenshot/<int:year>/months/", methods=["GET"])
def list_months(year: int):
    """
    Get list of available months for a specific year.

    Query parameters:
    - min_max_signal: Minimum maximum signal value to filter months
    """
    try:
        manager = get_screenshot_manager()
        min_max_signal = request.args.get("min_max_signal", type=float)

        # Get available dates with maximum signal filter
        dates = manager.get_available_dates(min_max_signal)

        # Extract months for the specified year
        months = sorted({d["month"] for d in dates if d["year"] == year}, reverse=True)

        return jsonify({"months": months})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@viewer_api.route("/api/screenshot/<int:year>/<int:month>/days/", methods=["GET"])
def list_days(year: int, month: int):
    """
    Get list of available days for a specific year and month.

    Query parameters:
    - min_max_signal: Minimum maximum signal value to filter days
    """
    try:
        manager = get_screenshot_manager()
        min_max_signal = request.args.get("min_max_signal", type=float)

        # Get available dates with maximum signal filter
        dates = manager.get_available_dates(min_max_signal)

        # Extract days for the specified year and month
        days = sorted({d["day"] for d in dates if d["year"] == year and d["month"] == month}, reverse=True)

        return jsonify({"days": days})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@viewer_api.route("/api/screenshot/<int:year>/<int:month>/<int:day>/", methods=["GET"])
def list_by_date(year: int, month: int, day: int):
    """
    Get screenshots for a specific date.

    Query parameters:
    - min_max_signal: Minimum maximum signal value to filter screenshots
    """
    try:
        manager = get_screenshot_manager()
        min_max_signal = request.args.get("min_max_signal", type=float)

        # Get screenshots with optional maximum signal filter
        screenshots = manager.get_screenshots_with_signal_filter(min_max_signal)

        # Filter by date
        files = [
            {
                "filename": s["filename"],
                "prefix": s["filename"].split("-")[0],
                "year": s["year"],
                "month": s["month"],
                "day": s["day"],
                "hour": s["hour"],
                "minute": s["minute"],
                "second": s["second"],
                "timestamp": s["timestamp"],
                "sta": s["sta"],
                "lta": s["lta"],
                "sta_lta_ratio": s["sta_lta_ratio"],
                "max_count": s["max_count"],
                "metadata": s["metadata"],
            }
            for s in screenshots
            if s["year"] == year and s["month"] == month and s["day"] == day
        ]

        return jsonify({"screenshots": files, "total": len(files)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _get_image_file_path(filename: str):
    """Get the actual file path for a given filename."""
    screenshots_dir = get_screenshots_path()

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
            return jsonify({"error": "File not found"}), 404

        file_path = Path(file_path_str)

        if file_path.stat().st_size == 0:
            return jsonify({"error": "File is empty"}), 404

        # Send file with optimal cache headers
        return send_file(
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
        return jsonify({"error": str(e)}), 500


@viewer_api.route("/api/screenshot/latest/", methods=["GET"])
def get_latest():
    """
    Get the most recent screenshot.

    Query parameters:
    - min_max_signal: Minimum maximum signal value to filter screenshots
    """
    try:
        manager = get_screenshot_manager()
        min_max_signal = request.args.get("min_max_signal", type=float)

        # Get screenshots with optional maximum signal filter
        screenshots = manager.get_screenshots_with_signal_filter(min_max_signal)

        if not screenshots:
            return jsonify({"error": "No screenshots found"}), 404

        # First one is already the latest (sorted by timestamp desc)
        latest = screenshots[0]

        return jsonify(
            {
                "filename": latest["filename"],
                "prefix": latest["filename"].split("-")[0],
                "year": latest["year"],
                "month": latest["month"],
                "day": latest["day"],
                "hour": latest["hour"],
                "minute": latest["minute"],
                "second": latest["second"],
                "timestamp": latest["timestamp"],
                "sta": latest["sta"],
                "lta": latest["lta"],
                "sta_lta_ratio": latest["sta_lta_ratio"],
                "max_count": latest["max_count"],
                "metadata": latest["metadata"],
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@viewer_api.route("/api/screenshot/statistics/", methods=["GET"])
def get_statistics():
    """
    Get signal value statistics for screenshots.

    Query parameters:
    - earthquake_only: If true, only include screenshots during earthquake windows
    """
    try:
        manager = get_screenshot_manager()
        quake_db_path = get_quake_db_path()
        earthquake_only = request.args.get("earthquake_only", "false").lower() == "true"

        stats = manager.get_signal_statistics(
            quake_db_path=quake_db_path,
            earthquake_only=earthquake_only,
        )

        # Add earthquake count
        if quake_db_path and quake_db_path.exists():
            from rsudp.quake.database import QuakeDatabase

            quake_db = QuakeDatabase(current_app.config["CONFIG"])
            stats["earthquake_count"] = quake_db.count_earthquakes()
        else:
            stats["earthquake_count"] = 0

        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@viewer_api.route("/api/screenshot/scan/", methods=["POST"])
def scan_screenshots():
    """
    Scan for new screenshot files and update cache.

    Uses a lock to prevent concurrent scans. If a scan is already in progress,
    returns immediately with a message indicating that.
    """
    global _is_scanning  # noqa: PLW0603

    # Try to acquire lock without blocking
    if not _scan_lock.acquire(blocking=False):
        return jsonify({"success": True, "message": "Scan already in progress", "skipped": True})

    try:
        if _is_scanning:
            return jsonify({"success": True, "message": "Scan already in progress", "skipped": True})

        _is_scanning = True
        manager = get_screenshot_manager()

        # Organize files and scan for new ones
        manager.organize_files()
        new_count = manager.scan_and_cache_all()

        return jsonify({"success": True, "new_files": new_count, "skipped": False})
    except Exception as e:
        import traceback

        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500
    finally:
        _is_scanning = False
        _scan_lock.release()


@viewer_api.route("/api/earthquake/crawl/", methods=["POST"])
def crawl_earthquake_data():
    """Trigger earthquake data crawl from JMA."""
    try:
        config = current_app.config["CONFIG"]
        new_count = crawl_earthquakes(config, min_intensity=3)
        return jsonify({"success": True, "new_earthquakes": new_count})
    except Exception as e:
        import traceback

        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@viewer_api.route("/api/earthquake/list/", methods=["GET"])
def list_earthquakes():
    """List all stored earthquakes."""
    try:
        from rsudp.quake.database import QuakeDatabase

        config = current_app.config["CONFIG"]
        quake_db = QuakeDatabase(config)
        earthquakes = quake_db.get_all_earthquakes(limit=100)
        return jsonify({"earthquakes": earthquakes, "total": len(earthquakes)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@viewer_api.route("/api/screenshot/clean/", methods=["POST"])
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
        import cleaner

        config = current_app.config["CONFIG"]

        # リクエストパラメータを取得
        data = request.get_json() or {}
        min_max_count = data.get("min_max_count", cleaner.DEFAULT_MIN_MAX_COUNT)
        time_window_minutes = data.get("time_window_minutes", cleaner.DEFAULT_TIME_WINDOW_MINUTES)
        min_magnitude = data.get("min_magnitude", cleaner.DEFAULT_MIN_MAGNITUDE)
        dry_run = data.get("dry_run", False)

        # 削除対象を取得
        to_delete = cleaner.get_screenshots_to_clean(
            config,
            min_max_count=min_max_count,
            time_window_minutes=time_window_minutes,
            min_magnitude=min_magnitude,
        )

        if dry_run:
            # dry-run モードでは削除対象のリストを返すだけ
            return jsonify(
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
        deleted_count = cleaner.delete_screenshots(config, to_delete, dry_run=False)

        return jsonify(
            {
                "success": True,
                "dry_run": False,
                "deleted_count": deleted_count,
            }
        )

    except Exception as e:
        import traceback

        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500
