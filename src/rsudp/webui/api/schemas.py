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
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int
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
