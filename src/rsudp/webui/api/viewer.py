"""Screenshot viewer API endpoints for rsudp web interface."""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from flask import Blueprint, current_app, jsonify, request, send_file
from rsudp.screenshot_manager import ScreenshotManager
import my_lib.flask_util

viewer_api = Blueprint("viewer_api", __name__, url_prefix="/rsudp")
blueprint = viewer_api  # Alias for compatibility with webui.py

# Global instance of ScreenshotManager
_screenshot_manager: Optional[ScreenshotManager] = None

def get_screenshot_manager() -> ScreenshotManager:
    """Get or create ScreenshotManager instance."""
    global _screenshot_manager
    if _screenshot_manager is None:
        config = current_app.config["CONFIG"]
        # Ensure cache path is set
        if "data" not in config:
            config["data"] = {}
        if "cache" not in config["data"]:
            config["data"]["cache"] = "data/cache.db"
        _screenshot_manager = ScreenshotManager(config)
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
            int(year), int(month), int(day), int(hour), int(minute), int(second), tzinfo=timezone.utc
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


@viewer_api.route("/api/screenshot/", methods=["GET"])
def list_screenshots():
    """
    List all screenshot files with parsed metadata.

    Returns files sorted by timestamp (newest first).
    Query parameters:
    - min_max_signal: Minimum maximum signal value to filter screenshots
    """
    try:
        manager = get_screenshot_manager()
        
        # Organize files if needed (moves files to date-based subdirectories)
        manager.organize_files()
        
        # Scan and cache any new files
        manager.scan_and_cache_all()
        
        # Get minimum maximum signal filter from query parameters
        min_max_signal = request.args.get("min_max_signal", type=float)
        
        # Get screenshots with optional maximum signal filter
        screenshots = manager.get_screenshots_with_signal_filter(min_max_signal)
        
        # Format for compatibility with existing frontend
        formatted_screenshots = []
        for s in screenshots:
            formatted_screenshots.append({
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
                "metadata": s["metadata"]
            })
        
        return jsonify({
            "screenshots": formatted_screenshots, 
            "total": len(formatted_screenshots), 
            "path": str(get_screenshots_path())
        })

    except Exception as e:
        import traceback

        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@viewer_api.route("/api/screenshot/years/", methods=["GET"])
def list_years():
    """Get list of available years.
    
    Query parameters:
    - min_max_signal: Minimum maximum signal value to filter years
    """
    try:
        manager = get_screenshot_manager()
        min_max_signal = request.args.get("min_max_signal", type=float)
        
        # Get available dates with maximum signal filter
        dates = manager.get_available_dates(min_max_signal)
        
        # Extract unique years
        years = sorted(set(d["year"] for d in dates), reverse=True)
        
        return jsonify({"years": years})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@viewer_api.route("/api/screenshot/<int:year>/months/", methods=["GET"])
def list_months(year: int):
    """Get list of available months for a specific year.
    
    Query parameters:
    - min_max_signal: Minimum maximum signal value to filter months
    """
    try:
        manager = get_screenshot_manager()
        min_max_signal = request.args.get("min_max_signal", type=float)
        
        # Get available dates with maximum signal filter
        dates = manager.get_available_dates(min_max_signal)
        
        # Extract months for the specified year
        months = sorted(
            set(d["month"] for d in dates if d["year"] == year), 
            reverse=True
        )
        
        return jsonify({"months": months})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@viewer_api.route("/api/screenshot/<int:year>/<int:month>/days/", methods=["GET"])
def list_days(year: int, month: int):
    """Get list of available days for a specific year and month.
    
    Query parameters:
    - min_max_signal: Minimum maximum signal value to filter days
    """
    try:
        manager = get_screenshot_manager()
        min_max_signal = request.args.get("min_max_signal", type=float)
        
        # Get available dates with maximum signal filter
        dates = manager.get_available_dates(min_max_signal)
        
        # Extract days for the specified year and month
        days = sorted(
            set(d["day"] for d in dates 
                if d["year"] == year and d["month"] == month), 
            reverse=True
        )
        
        return jsonify({"days": days})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@viewer_api.route("/api/screenshot/<int:year>/<int:month>/<int:day>/", methods=["GET"])
def list_by_date(year: int, month: int, day: int):
    """Get screenshots for a specific date.
    
    Query parameters:
    - min_max_signal: Minimum maximum signal value to filter screenshots
    """
    try:
        manager = get_screenshot_manager()
        min_max_signal = request.args.get("min_max_signal", type=float)
        
        # Get screenshots with optional maximum signal filter
        screenshots = manager.get_screenshots_with_signal_filter(min_max_signal)
        
        # Filter by date
        files = []
        for s in screenshots:
            if s["year"] == year and s["month"] == month and s["day"] == day:
                files.append({
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
                    "metadata": s["metadata"]
                })
        
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
    cache_control="public, max-age=31536000, immutable"
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
        response = send_file(
            str(file_path),
            mimetype="image/png",
            as_attachment=False,
            download_name=None,
            # Disable Flask's built-in conditional requests since we're using ETag
            conditional=False,
            # Set max age to 1 year since screenshots are immutable
            max_age=31536000,  # 1 year in seconds
        )

        return response

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@viewer_api.route("/api/screenshot/latest/", methods=["GET"])
def get_latest():
    """Get the most recent screenshot.
    
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
        
        return jsonify({
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
            "metadata": latest["metadata"]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@viewer_api.route("/api/screenshot/statistics/", methods=["GET"])
def get_statistics():
    """Get signal value statistics for all screenshots."""
    try:
        manager = get_screenshot_manager()
        stats = manager.get_signal_statistics()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
