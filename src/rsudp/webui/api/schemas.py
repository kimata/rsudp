"""
API schemas for rsudp web interface.

This module defines Pydantic schemas that mirror the TypeScript interfaces
in frontend/src/types.ts to ensure frontend-backend API consistency.
"""

from pydantic import BaseModel, ConfigDict


class Earthquake(BaseModel):
    """
    Earthquake data schema.

    Mirrors TypeScript interface: frontend/src/types.ts:Earthquake
    """

    model_config = ConfigDict(strict=True)

    id: int
    event_id: str
    detected_at: str
    latitude: float
    longitude: float
    magnitude: float
    depth: int
    epicenter_name: str
    max_intensity: str | None = None


class Screenshot(BaseModel):
    """
    Screenshot metadata schema.

    Mirrors TypeScript interface: frontend/src/types.ts:Screenshot
    """

    model_config = ConfigDict(strict=True)

    filename: str
    prefix: str
    timestamp: str
    sta: float | None = None
    lta: float | None = None
    sta_lta_ratio: float | None = None
    max_count: float
    metadata: str | None = None
    earthquake: Earthquake | None = None


class ScreenshotListResponse(BaseModel):
    """
    Response schema for screenshot list endpoints.

    Mirrors TypeScript interface: frontend/src/types.ts:ScreenshotListResponse
    """

    model_config = ConfigDict(strict=True)

    screenshots: list[Screenshot]
    total: int


class ScreenshotListWithPathResponse(ScreenshotListResponse):
    """Extended response schema including path (for /api/screenshot/)."""

    path: str


class StatisticsResponse(BaseModel):
    """
    Response schema for statistics endpoint.

    Mirrors TypeScript interface: frontend/src/types.ts:StatisticsResponse
    """

    model_config = ConfigDict(strict=True)

    total: int
    absolute_total: int
    min_signal: float | None = None
    max_signal: float | None = None
    avg_signal: float | None = None
    with_signal: int
    earthquake_count: int | None = None


class ErrorResponse(BaseModel):
    """Response schema for error responses."""

    model_config = ConfigDict(strict=True)

    error: str
    traceback: str | None = None


class SysInfo(BaseModel):
    """
    System information schema.

    Mirrors TypeScript interface: frontend/src/types.ts:SysInfo
    """

    model_config = ConfigDict(strict=True)

    date: str
    timezone: str
    image_build_date: str
    uptime: str
    load_average: str
    cpu_usage: float
    memory_usage_percent: float
    memory_free_mb: float
    disk_usage_percent: float
    disk_free_mb: float
    process_count: int
    cpu_temperature: float | None = None


# ============================================================================
# Request Parameter Schemas (for flask-pydantic @validate())
# ============================================================================


class ScreenshotListQuery(BaseModel):
    """Query parameters for GET /api/screenshot/."""

    min_max_signal: float | None = None
    earthquake_only: bool = False
    min_magnitude: float | None = None


class MinMaxSignalQuery(BaseModel):
    """Query parameters for endpoints that only use min_max_signal filter."""

    min_max_signal: float | None = None


class EarthquakeOnlyQuery(BaseModel):
    """Query parameters for GET /api/screenshot/statistics/."""

    earthquake_only: bool = False
    min_magnitude: float | None = None


class CleanRequest(BaseModel):
    """Request body for POST /api/screenshot/clean/."""

    min_max_count: int = 300000
    time_window_minutes: int = 10
    min_magnitude: float = 3.0
    dry_run: bool = False


class IndexQuery(BaseModel):
    """Query parameters for GET / (index with OGP)."""

    file: str | None = None


class DaysQuery(BaseModel):
    """Query parameters for statistics endpoints that accept a days range."""

    days: int = 90


# ============================================================================
# Statistics Response Schemas
# ============================================================================


class DailyCount(BaseModel):
    """Daily screenshot count (JST date)."""

    model_config = ConfigDict(strict=True)

    date: str
    count: int


class DailyStatisticsResponse(BaseModel):
    """Response schema for GET /api/statistics/daily."""

    model_config = ConfigDict(strict=True)

    data: list[DailyCount]


class DistributionBin(BaseModel):
    """A single histogram bin for max_count distribution."""

    model_config = ConfigDict(strict=True)

    label: str
    min: float
    max: float | None = None
    count: int


class DistributionResponse(BaseModel):
    """Response schema for GET /api/statistics/distribution."""

    model_config = ConfigDict(strict=True)

    bins: list[DistributionBin]


class AssociationCount(BaseModel):
    """Daily total and earthquake-matched counts (JST date)."""

    model_config = ConfigDict(strict=True)

    date: str
    total: int
    matched: int


class AssociationResponse(BaseModel):
    """Response schema for GET /api/statistics/association."""

    model_config = ConfigDict(strict=True)

    data: list[AssociationCount]


class StationLocation(BaseModel):
    """Observation station location."""

    model_config = ConfigDict(strict=True)

    latitude: float
    longitude: float


class SensitivityPoint(BaseModel):
    """A single detection-sensitivity data point (one earthquake)."""

    model_config = ConfigDict(strict=True)

    event_id: str
    epicenter_name: str
    distance_km: float
    magnitude: float
    depth: int
    max_count: float
    detected_at: str


class SensitivityResponse(BaseModel):
    """Response schema for GET /api/statistics/sensitivity."""

    model_config = ConfigDict(strict=True)

    station: StationLocation | None = None
    points: list[SensitivityPoint]
