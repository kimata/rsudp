"""
Screenshot viewer API endpoints for rsudp web interface.
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from flask import Blueprint, jsonify, send_file, current_app

viewer_api = Blueprint('viewer_api', __name__, url_prefix='/rsudp')
blueprint = viewer_api  # Alias for compatibility with webui.py


def parse_filename(filename: str) -> Optional[Dict]:
    """
    Parse screenshot filename to extract timestamp information.
    Format: PREFIX-YYYY-MM-DD-HHMMSS.png (e.g., SHAKE-2025-08-12-104039.png)
    """
    pattern = r'^(.+?)-(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})(\d{2})\.png$'
    match = re.match(pattern, filename)
    
    if not match:
        return None
    
    prefix, year, month, day, hour, minute, second = match.groups()
    
    return {
        'filename': filename,
        'prefix': prefix,
        'year': int(year),
        'month': int(month),
        'day': int(day),
        'hour': int(hour),
        'minute': int(minute),
        'second': int(second),
        'timestamp': datetime(
            int(year), int(month), int(day),
            int(hour), int(minute), int(second)
        ).isoformat() + 'Z'  # UTC timestamp
    }


def get_screenshots_path() -> Path:
    """Get the screenshots directory path from config."""
    path = Path(current_app.config["CONFIG"]["plot"]["screenshot"]["path"])
    
    # 相対パスの場合は、プロジェクトルートから解決
    if not path.is_absolute():
        # srcディレクトリの親ディレクトリ（プロジェクトルート）を基準にする
        import os
        project_root = Path(os.getcwd()).parent if Path(os.getcwd()).name == 'src' else Path(os.getcwd())
        path = project_root / path
    
    return path


@viewer_api.route('/api/screenshot/', methods=['GET'])
def list_screenshots():
    """
    List all screenshot files with parsed metadata.
    Returns files sorted by timestamp (newest first).
    """
    try:
        screenshots_dir = get_screenshots_path()
        
        if not screenshots_dir.exists():
            return jsonify({
                'error': 'Screenshots directory not found', 
                'path': str(screenshots_dir)
            }), 404
        
        files = []
        for file_path in screenshots_dir.glob('*.png'):
            if file_path.is_file() and file_path.stat().st_size > 0:
                parsed = parse_filename(file_path.name)
                if parsed:
                    files.append(parsed)
        
        # Sort by timestamp (newest first)
        files.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify({
            'screenshots': files,
            'total': len(files),
            'path': str(screenshots_dir)
        })
    
    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@viewer_api.route('/api/screenshot/years/', methods=['GET'])
def list_years():
    """Get list of available years."""
    try:
        screenshots_dir = get_screenshots_path()
        
        if not screenshots_dir.exists():
            return jsonify({'years': []})
        
        years = set()
        for file_path in screenshots_dir.glob('*.png'):
            if file_path.is_file() and file_path.stat().st_size > 0:
                parsed = parse_filename(file_path.name)
                if parsed:
                    years.add(parsed['year'])
        
        return jsonify({'years': sorted(years, reverse=True)})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@viewer_api.route('/api/screenshot/<int:year>/months/', methods=['GET'])
def list_months(year: int):
    """Get list of available months for a specific year."""
    try:
        screenshots_dir = get_screenshots_path()
        
        if not screenshots_dir.exists():
            return jsonify({'months': []})
        
        months = set()
        for file_path in screenshots_dir.glob('*.png'):
            if file_path.is_file() and file_path.stat().st_size > 0:
                parsed = parse_filename(file_path.name)
                if parsed and parsed['year'] == year:
                    months.add(parsed['month'])
        
        return jsonify({'months': sorted(months, reverse=True)})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@viewer_api.route('/api/screenshot/<int:year>/<int:month>/days/', methods=['GET'])
def list_days(year: int, month: int):
    """Get list of available days for a specific year and month."""
    try:
        screenshots_dir = get_screenshots_path()
        
        if not screenshots_dir.exists():
            return jsonify({'days': []})
        
        days = set()
        for file_path in screenshots_dir.glob('*.png'):
            if file_path.is_file() and file_path.stat().st_size > 0:
                parsed = parse_filename(file_path.name)
                if parsed and parsed['year'] == year and parsed['month'] == month:
                    days.add(parsed['day'])
        
        return jsonify({'days': sorted(days, reverse=True)})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@viewer_api.route('/api/screenshot/<int:year>/<int:month>/<int:day>/', methods=['GET'])
def list_by_date(year: int, month: int, day: int):
    """Get screenshots for a specific date."""
    try:
        screenshots_dir = get_screenshots_path()
        
        if not screenshots_dir.exists():
            return jsonify({'screenshots': []})
        
        files = []
        for file_path in screenshots_dir.glob('*.png'):
            if file_path.is_file() and file_path.stat().st_size > 0:
                parsed = parse_filename(file_path.name)
                if (parsed and 
                    parsed['year'] == year and 
                    parsed['month'] == month and 
                    parsed['day'] == day):
                    files.append(parsed)
        
        # Sort by timestamp (newest first)
        files.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify({
            'screenshots': files,
            'total': len(files)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@viewer_api.route('/api/screenshot/image/<path:filename>', methods=['GET'])
def get_image(filename: str):
    """Serve a specific screenshot image."""
    try:
        screenshots_dir = get_screenshots_path()
        file_path = screenshots_dir / filename
        
        if not file_path.exists() or not file_path.is_file():
            return jsonify({'error': 'File not found'}), 404
        
        if file_path.stat().st_size == 0:
            return jsonify({'error': 'File is empty'}), 404
        
        return send_file(
            str(file_path), 
            mimetype='image/png',
            as_attachment=False,
            download_name=None
        )
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@viewer_api.route('/api/screenshot/latest/', methods=['GET'])
def get_latest():
    """Get the most recent screenshot."""
    try:
        screenshots_dir = get_screenshots_path()
        
        if not screenshots_dir.exists():
            return jsonify({'error': 'Screenshots directory not found'}), 404
        
        latest = None
        latest_time = None
        
        for file_path in screenshots_dir.glob('*.png'):
            if file_path.is_file() and file_path.stat().st_size > 0:
                parsed = parse_filename(file_path.name)
                if parsed:
                    timestamp = parsed['timestamp']
                    if latest_time is None or timestamp > latest_time:
                        latest = parsed
                        latest_time = timestamp
        
        if latest is None:
            return jsonify({'error': 'No screenshots found'}), 404
        
        return jsonify(latest)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
