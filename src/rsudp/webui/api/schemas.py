"""
API schemas for rsudp web interface.

This module defines Pydantic schemas that mirror the TypeScript interfaces
in react/src/types.ts to ensure frontend-backend API consistency.
"""

from pydantic import BaseModel, ConfigDict


class Screenshot(BaseModel):
    """
    Screenshot metadata schema.

    Mirrors TypeScript interface: react/src/types.ts:Screenshot
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
    metadata: str | None = None


class ScreenshotListResponse(BaseModel):
    """
    Response schema for screenshot list endpoints.

    Mirrors TypeScript interface: react/src/types.ts:ScreenshotListResponse
    """

    model_config = ConfigDict(strict=True)

    screenshots: list[Screenshot]
    total: int


class ScreenshotListWithPathResponse(ScreenshotListResponse):
    """Extended response schema including path (for /api/screenshot/)."""

    path: str


class YearsResponse(BaseModel):
    """
    Response schema for years endpoint.

    Mirrors TypeScript interface: react/src/types.ts:YearsResponse
    """

    model_config = ConfigDict(strict=True)

    years: list[int]


class MonthsResponse(BaseModel):
    """
    Response schema for months endpoint.

    Mirrors TypeScript interface: react/src/types.ts:MonthsResponse
    """

    model_config = ConfigDict(strict=True)

    months: list[int]


class DaysResponse(BaseModel):
    """
    Response schema for days endpoint.

    Mirrors TypeScript interface: react/src/types.ts:DaysResponse
    """

    model_config = ConfigDict(strict=True)

    days: list[int]


class StatisticsResponse(BaseModel):
    """
    Response schema for statistics endpoint.

    Mirrors TypeScript interface: react/src/types.ts:StatisticsResponse
    """

    model_config = ConfigDict(strict=True)

    total: int
    min_sta: float | None = None
    max_sta: float | None = None
    avg_sta: float | None = None
    with_sta: int


class ErrorResponse(BaseModel):
    """Response schema for error responses."""

    model_config = ConfigDict(strict=True)

    error: str
    traceback: str | None = None


class SysInfo(BaseModel):
    """
    System information schema.

    Mirrors TypeScript interface: react/src/types.ts:SysInfo
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
