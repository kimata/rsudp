"""Screenshot management with metadata caching and file organization."""

import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from PIL import Image
from PIL.PngImagePlugin import PngInfo


class ScreenshotManager:
    """Manages screenshot files with metadata caching and organization."""
    
    def __init__(self, config: dict):
        self.config = config
        self.screenshot_path = Path(config["plot"]["screenshot"]["path"])
        self.cache_path = Path(config.get("data", {}).get("cache", "data/cache.db"))
        
        # Ensure cache directory exists
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database for metadata caching."""
        with sqlite3.connect(self.cache_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS screenshot_metadata (
                    filename TEXT PRIMARY KEY,
                    filepath TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    month INTEGER NOT NULL,
                    day INTEGER NOT NULL,
                    hour INTEGER NOT NULL,
                    minute INTEGER NOT NULL,
                    second INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    sta_value REAL,
                    lta_value REAL,
                    sta_lta_ratio REAL,
                    max_count REAL,
                    created_at REAL NOT NULL,
                    file_size INTEGER NOT NULL,
                    metadata_raw TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_screenshot_date 
                ON screenshot_metadata(year, month, day)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_screenshot_sta 
                ON screenshot_metadata(sta_value)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_screenshot_timestamp 
                ON screenshot_metadata(timestamp)
            """)
    
    def organize_files(self):
        """Organize screenshot files by date into subdirectories."""
        if not self.screenshot_path.exists():
            return
        
        # Get all PNG files in root directory
        for file_path in self.screenshot_path.glob("*.png"):
            if not file_path.is_file():
                continue
            
            # Parse filename to get date
            parsed = self._parse_filename(file_path.name)
            if not parsed:
                continue
            
            # Create date-based subdirectory (YYYY/MM/DD)
            date_dir = self.screenshot_path / str(parsed["year"]) / f"{parsed['month']:02d}" / f"{parsed['day']:02d}"
            date_dir.mkdir(parents=True, exist_ok=True)
            
            # Move file to subdirectory
            new_path = date_dir / file_path.name
            if not new_path.exists():
                shutil.move(str(file_path), str(new_path))
                
                # Update cache with new file location
                self._cache_file_metadata(new_path)
    
    def _parse_filename(self, filename: str) -> Optional[dict]:
        """Parse screenshot filename to extract timestamp information."""
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
                int(year), int(month), int(day), 
                int(hour), int(minute), int(second), 
                tzinfo=timezone.utc
            ).isoformat(),
        }
    
    def _extract_metadata(self, file_path: Path) -> dict:
        """Extract metadata from PNG file including STA values."""
        metadata = {}
        
        try:
            # Open image with PIL
            with Image.open(file_path) as img:
                # Get PNG metadata
                info = img.info
                
                # Check for Description field in PNG metadata
                description = info.get('Description', '')
                
                if description:
                    metadata['raw'] = description
                    
                    # Parse STA, LTA, ratio, and MaxCount values
                    sta_match = re.search(r'STA=([0-9.]+)', description)
                    lta_match = re.search(r'LTA=([0-9.]+)', description)
                    ratio_match = re.search(r'STA/LTA=([0-9.]+)', description)
                    max_count_match = re.search(r'MaxCount=([0-9.]+)', description)
                    
                    if sta_match:
                        metadata['sta'] = float(sta_match.group(1))
                    if lta_match:
                        metadata['lta'] = float(lta_match.group(1))
                    if ratio_match:
                        metadata['sta_lta_ratio'] = float(ratio_match.group(1))
                    if max_count_match:
                        metadata['max_count'] = float(max_count_match.group(1))
                
                # Also check Comment field if Description is not found
                if not description and 'Comment' in info:
                    comment = info.get('Comment', '')
                    # Store comment for reference
                    if comment and 'raw' not in metadata:
                        metadata['comment'] = comment
                        
        except Exception as e:
            print(f"Error extracting metadata from {file_path}: {e}")
        
        return metadata
    
    def _cache_file_metadata(self, file_path: Path):
        """Cache file metadata in SQLite database."""
        if not file_path.exists():
            return
        
        parsed = self._parse_filename(file_path.name)
        if not parsed:
            return
        
        # Extract metadata
        metadata = self._extract_metadata(file_path)
        
        # Get file stats
        stat = file_path.stat()
        
        # Store in database
        with sqlite3.connect(self.cache_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO screenshot_metadata 
                (filename, filepath, year, month, day, hour, minute, second, 
                 timestamp, sta_value, lta_value, sta_lta_ratio, max_count,
                 created_at, file_size, metadata_raw)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                file_path.name,
                str(file_path.relative_to(self.screenshot_path)),
                parsed["year"],
                parsed["month"],
                parsed["day"],
                parsed["hour"],
                parsed["minute"],
                parsed["second"],
                parsed["timestamp"],
                metadata.get("sta"),
                metadata.get("lta"),
                metadata.get("sta_lta_ratio"),
                metadata.get("max_count"),
                stat.st_ctime,
                stat.st_size,
                metadata.get("raw")
            ))
    
    def scan_and_cache_all(self):
        """Scan all screenshot files and update cache."""
        if not self.screenshot_path.exists():
            return
        
        # Get all PNG files recursively
        for file_path in self.screenshot_path.rglob("*.png"):
            if not file_path.is_file():
                continue
            
            # Check if already cached
            with sqlite3.connect(self.cache_path) as conn:
                cursor = conn.execute(
                    "SELECT file_size FROM screenshot_metadata WHERE filename = ?",
                    (file_path.name,)
                )
                row = cursor.fetchone()
                
                # Skip if already cached and file size hasn't changed
                if row and row[0] == file_path.stat().st_size:
                    continue
            
            # Cache the file metadata
            self._cache_file_metadata(file_path)
    
    def get_screenshots_with_signal_filter(self, min_max_signal: Optional[float] = None):
        """Get screenshots filtered by minimum maximum signal value (STA)."""
        with sqlite3.connect(self.cache_path) as conn:
            query = """
                SELECT filename, filepath, year, month, day, hour, minute, second,
                       timestamp, sta_value, lta_value, sta_lta_ratio, max_count, metadata_raw
                FROM screenshot_metadata
            """
            params = []
            
            if min_max_signal is not None:
                query += " WHERE sta_value >= ?"
                params.append(min_max_signal)
            
            query += " ORDER BY timestamp DESC"
            
            cursor = conn.execute(query, params)
            
            screenshots = []
            for row in cursor:
                screenshots.append({
                    "filename": row[0],
                    "filepath": row[1],
                    "year": row[2],
                    "month": row[3],
                    "day": row[4],
                    "hour": row[5],
                    "minute": row[6],
                    "second": row[7],
                    "timestamp": row[8],
                    "sta": row[9],
                    "lta": row[10],
                    "sta_lta_ratio": row[11],
                    "max_count": row[12],
                    "metadata": row[13]
                })
            
            return screenshots
    
    def get_available_dates(self, min_max_signal: Optional[float] = None):
        """Get available dates that have screenshots with minimum maximum signal value."""
        with sqlite3.connect(self.cache_path) as conn:
            query = """
                SELECT DISTINCT year, month, day
                FROM screenshot_metadata
            """
            params = []
            
            if min_max_signal is not None:
                query += " WHERE sta_value >= ?"
                params.append(min_max_signal)
            
            query += " ORDER BY year DESC, month DESC, day DESC"
            
            cursor = conn.execute(query, params)
            
            dates = []
            for row in cursor:
                dates.append({
                    "year": row[0],
                    "month": row[1],
                    "day": row[2]
                })
            
            return dates
    
    def get_signal_statistics(self):
        """Get signal value statistics (STA values)."""
        with sqlite3.connect(self.cache_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    MIN(sta_value) as min_signal,
                    MAX(sta_value) as max_signal,
                    AVG(sta_value) as avg_signal,
                    COUNT(CASE WHEN sta_value IS NOT NULL THEN 1 END) as with_signal
                FROM screenshot_metadata
            """)
            
            row = cursor.fetchone()
            return {
                "total": row[0],
                "min_signal": row[1],
                "max_signal": row[2],
                "avg_signal": row[3],
                "with_signal": row[4]
            }