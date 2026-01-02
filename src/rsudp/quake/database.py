"""Earthquake database management with SQLite."""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Schema file path (relative to project root)
SCHEMA_FILE = Path(__file__).parent.parent.parent.parent / "schema" / "sqlite.schema"


class QuakeDatabase:
    """Manages earthquake data storage in SQLite."""

    def __init__(self, config: dict):
        """Initialize the database with configuration."""
        self.config = config
        self.db_path = Path(config.get("data", {}).get("quake", "data/quake.db"))

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database for earthquake data."""
        with sqlite3.connect(self.db_path) as conn:
            # Read and execute schema from file
            schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
            conn.executescript(schema_sql)

    def insert_earthquake(  # noqa: PLR0913
        self,
        event_id: str,
        detected_at: datetime,
        latitude: float,
        longitude: float,
        magnitude: float,
        depth: int,
        epicenter_name: str,
        max_intensity: str | None = None,
    ) -> bool:
        """
        Insert or update earthquake data.

        Returns True if a new record was inserted, False if updated.
        """
        now = datetime.now(tz=UTC).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            # Check if record exists
            cursor = conn.execute("SELECT id FROM earthquakes WHERE event_id = ?", (event_id,))
            existing = cursor.fetchone()

            if existing:
                # Update existing record
                conn.execute(
                    """
                    UPDATE earthquakes SET
                        detected_at = ?,
                        latitude = ?,
                        longitude = ?,
                        magnitude = ?,
                        depth = ?,
                        epicenter_name = ?,
                        max_intensity = ?,
                        updated_at = ?
                    WHERE event_id = ?
                """,
                    (
                        detected_at.isoformat(),
                        latitude,
                        longitude,
                        magnitude,
                        depth,
                        epicenter_name,
                        max_intensity,
                        now,
                        event_id,
                    ),
                )
                return False
            # Insert new record
            conn.execute(
                """
                INSERT INTO earthquakes
                (event_id, detected_at, latitude, longitude, magnitude,
                 depth, epicenter_name, max_intensity, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    event_id,
                    detected_at.isoformat(),
                    latitude,
                    longitude,
                    magnitude,
                    depth,
                    epicenter_name,
                    max_intensity,
                    now,
                    now,
                ),
            )
            return True

    def get_earthquake_for_timestamp(
        self,
        timestamp: datetime,
        before_seconds: int = 30,
        after_seconds: int = 240,
    ) -> dict | None:
        """
        Get earthquake that matches a given timestamp.

        The timestamp should be within [earthquake_time - before_seconds,
        earthquake_time + after_seconds].

        Args:
            timestamp: The timestamp to search for
            before_seconds: Seconds before earthquake to include (default: 30)
            after_seconds: Seconds after earthquake to include (default: 240 = 4 minutes)

        Returns:
            Dictionary with earthquake data or None if not found

        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM earthquakes
                WHERE datetime(detected_at) BETWEEN
                    datetime(?, '-' || ? || ' seconds') AND
                    datetime(?, '+' || ? || ' seconds')
                ORDER BY ABS(julianday(detected_at) - julianday(?))
                LIMIT 1
            """,
                (
                    timestamp.isoformat(),
                    after_seconds,
                    timestamp.isoformat(),
                    before_seconds,
                    timestamp.isoformat(),
                ),
            )
            row = cursor.fetchone()

            if row:
                return {
                    "id": row["id"],
                    "event_id": row["event_id"],
                    "detected_at": row["detected_at"],
                    "latitude": row["latitude"],
                    "longitude": row["longitude"],
                    "magnitude": row["magnitude"],
                    "depth": row["depth"],
                    "epicenter_name": row["epicenter_name"],
                    "max_intensity": row["max_intensity"],
                }
            return None

    def get_all_earthquakes(self, limit: int = 100) -> list[dict]:
        """Get all earthquakes, ordered by detection time (newest first)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM earthquakes
                ORDER BY detected_at DESC
                LIMIT ?
            """,
                (limit,),
            )

            return [dict(row) for row in cursor.fetchall()]

    def get_earthquake_time_ranges(
        self,
        before_seconds: int = 30,
        after_seconds: int = 240,
    ) -> list[tuple[datetime, datetime, dict]]:
        """
        Get time ranges for all earthquakes.

        Returns a list of tuples: (start_time, end_time, earthquake_data)
        """
        earthquakes = self.get_all_earthquakes(limit=1000)
        ranges = []

        for eq in earthquakes:
            detected_at = datetime.fromisoformat(eq["detected_at"])
            start_time = detected_at - timedelta(seconds=before_seconds)
            end_time = detected_at + timedelta(seconds=after_seconds)
            ranges.append((start_time, end_time, eq))

        return ranges

    def count_earthquakes(self) -> int:
        """Get total number of earthquakes in database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM earthquakes")
            return cursor.fetchone()[0]
