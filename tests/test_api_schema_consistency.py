# ruff: noqa: S101, TRY003, EM102
"""
API schema consistency tests between frontend (TypeScript) and backend (Python).

This module verifies that:
1. Pydantic schemas match the TypeScript interfaces in react/src/types.ts
2. API responses conform to the defined schemas
"""

import json
import re
from pathlib import Path
from typing import Any, get_args, get_origin

import pytest
from pydantic import BaseModel, ValidationError

from rsudp.webui.api.schemas import (
    DaysResponse,
    ErrorResponse,
    MonthsResponse,
    Screenshot,
    ScreenshotListResponse,
    ScreenshotListWithPathResponse,
    StatisticsResponse,
    SysInfo,
    YearsResponse,
)


class TestSchemaFieldConsistency:
    """Test that Pydantic schemas match TypeScript interfaces."""

    @pytest.fixture
    def typescript_types(self) -> dict[str, dict[str, Any]]:
        """Parse TypeScript interfaces from react/src/types.ts."""
        types_file = Path(__file__).parent.parent / "react" / "src" / "types.ts"
        content = types_file.read_text()

        interfaces = {}
        interface_pattern = r"export interface (\w+) \{([^}]+)\}"

        for match in re.finditer(interface_pattern, content):
            interface_name = match.group(1)
            body = match.group(2)

            fields = {}
            field_pattern = r"(\w+)(\?)?:\s*([^;]+);"

            for field_match in re.finditer(field_pattern, body):
                field_name = field_match.group(1)
                is_optional = field_match.group(2) == "?"
                ts_type = field_match.group(3).strip()
                fields[field_name] = {"type": ts_type, "optional": is_optional}

            interfaces[interface_name] = fields

        return interfaces

    def _ts_type_to_python(self, ts_type: str) -> set[type]:
        """Convert TypeScript type to Python type(s)."""
        type_mapping = {
            "string": {str},
            "number": {int, float},
            "boolean": {bool},
            "number[]": {list},
            "Screenshot[]": {list},
        }
        return type_mapping.get(ts_type, {object})

    def _get_pydantic_field_type(self, model: type[BaseModel], field_name: str) -> tuple[type, bool]:
        """Get the type and optionality of a Pydantic model field."""
        field_info = model.model_fields.get(field_name)
        if field_info is None:
            raise ValueError(f"Field {field_name} not found in {model.__name__}")

        annotation = field_info.annotation
        is_optional = False

        origin = get_origin(annotation)
        if origin is type(None) or (hasattr(origin, "__origin__") and origin.__origin__ is type(None)):
            is_optional = True
        elif str(annotation).startswith("typing.Optional") or str(annotation).startswith("Optional"):
            is_optional = True
            args = get_args(annotation)
            if args:
                annotation = args[0]

        if origin is list or str(annotation).startswith("list"):
            return list, is_optional

        if annotation in (int, float, str, bool):
            return annotation, is_optional

        return object, is_optional

    def test_screenshot_schema_matches_typescript(self, typescript_types):
        """Verify Screenshot schema matches TypeScript interface."""
        ts_screenshot = typescript_types.get("Screenshot")
        assert ts_screenshot is not None, "Screenshot interface not found in TypeScript"

        for field_name, ts_field in ts_screenshot.items():
            assert field_name in Screenshot.model_fields, (
                f"Field '{field_name}' missing in Pydantic Screenshot"
            )

            py_type, is_optional = self._get_pydantic_field_type(Screenshot, field_name)

            expected_types = self._ts_type_to_python(ts_field["type"])
            assert py_type in expected_types or any(
                issubclass(py_type, t) if isinstance(t, type) else False for t in expected_types
            ), f"Field '{field_name}' type mismatch: Python={py_type}, TypeScript={ts_field['type']}"

            if ts_field["optional"]:
                assert is_optional, f"Field '{field_name}' should be optional in Pydantic"

        for field_name in Screenshot.model_fields:
            assert field_name in ts_screenshot, (
                f"Extra field '{field_name}' in Pydantic Screenshot not in TypeScript"
            )

    def test_screenshot_list_response_schema_matches_typescript(self, typescript_types):
        """Verify ScreenshotListResponse schema matches TypeScript interface."""
        ts_response = typescript_types.get("ScreenshotListResponse")
        assert ts_response is not None, "ScreenshotListResponse interface not found in TypeScript"

        for field_name in ts_response:
            assert field_name in ScreenshotListResponse.model_fields, (
                f"Field '{field_name}' missing in Pydantic ScreenshotListResponse"
            )

    def test_years_response_schema_matches_typescript(self, typescript_types):
        """Verify YearsResponse schema matches TypeScript interface."""
        ts_response = typescript_types.get("YearsResponse")
        assert ts_response is not None, "YearsResponse interface not found in TypeScript"

        for field_name in ts_response:
            assert field_name in YearsResponse.model_fields, (
                f"Field '{field_name}' missing in Pydantic YearsResponse"
            )

    def test_months_response_schema_matches_typescript(self, typescript_types):
        """Verify MonthsResponse schema matches TypeScript interface."""
        ts_response = typescript_types.get("MonthsResponse")
        assert ts_response is not None, "MonthsResponse interface not found in TypeScript"

        for field_name in ts_response:
            assert field_name in MonthsResponse.model_fields, (
                f"Field '{field_name}' missing in Pydantic MonthsResponse"
            )

    def test_days_response_schema_matches_typescript(self, typescript_types):
        """Verify DaysResponse schema matches TypeScript interface."""
        ts_response = typescript_types.get("DaysResponse")
        assert ts_response is not None, "DaysResponse interface not found in TypeScript"

        for field_name in ts_response:
            assert field_name in DaysResponse.model_fields, (
                f"Field '{field_name}' missing in Pydantic DaysResponse"
            )

    def test_statistics_response_schema_matches_typescript(self, typescript_types):
        """Verify StatisticsResponse schema matches TypeScript interface."""
        ts_response = typescript_types.get("StatisticsResponse")
        assert ts_response is not None, "StatisticsResponse interface not found in TypeScript"

        for field_name in ts_response:
            assert field_name in StatisticsResponse.model_fields, (
                f"Field '{field_name}' missing in Pydantic StatisticsResponse"
            )

    def test_sysinfo_schema_matches_typescript(self, typescript_types):
        """Verify SysInfo schema matches TypeScript interface."""
        ts_response = typescript_types.get("SysInfo")
        assert ts_response is not None, "SysInfo interface not found in TypeScript"

        for field_name in ts_response:
            assert field_name in SysInfo.model_fields, f"Field '{field_name}' missing in Pydantic SysInfo"


class TestSchemaValidation:
    """Test that schemas properly validate data."""

    def test_screenshot_valid_data(self):
        """Test Screenshot schema accepts valid data."""
        data = {
            "filename": "SHAKE-2025-01-15-103045.png",
            "prefix": "SHAKE",
            "year": 2025,
            "month": 1,
            "day": 15,
            "hour": 10,
            "minute": 30,
            "second": 45,
            "timestamp": "2025-01-15T10:30:45+00:00",
            "sta": 1.5,
            "lta": 0.8,
            "sta_lta_ratio": 1.875,
            "metadata": "test metadata",
        }
        screenshot = Screenshot(**data)
        assert screenshot.filename == data["filename"]
        assert screenshot.sta == 1.5

    def test_screenshot_optional_fields(self):
        """Test Screenshot schema allows optional fields to be None."""
        data = {
            "filename": "SHAKE-2025-01-15-103045.png",
            "prefix": "SHAKE",
            "year": 2025,
            "month": 1,
            "day": 15,
            "hour": 10,
            "minute": 30,
            "second": 45,
            "timestamp": "2025-01-15T10:30:45+00:00",
        }
        screenshot = Screenshot(**data)
        assert screenshot.sta is None
        assert screenshot.lta is None
        assert screenshot.sta_lta_ratio is None
        assert screenshot.metadata is None

    def test_screenshot_invalid_type_raises_error(self):
        """Test Screenshot schema rejects invalid types."""
        data = {
            "filename": "SHAKE-2025-01-15-103045.png",
            "prefix": "SHAKE",
            "year": "not a number",  # Should be int
            "month": 1,
            "day": 15,
            "hour": 10,
            "minute": 30,
            "second": 45,
            "timestamp": "2025-01-15T10:30:45+00:00",
        }
        with pytest.raises(ValidationError):
            Screenshot(**data)

    def test_screenshot_list_response_valid(self):
        """Test ScreenshotListResponse schema accepts valid data."""
        data = {
            "screenshots": [
                {
                    "filename": "SHAKE-2025-01-15-103045.png",
                    "prefix": "SHAKE",
                    "year": 2025,
                    "month": 1,
                    "day": 15,
                    "hour": 10,
                    "minute": 30,
                    "second": 45,
                    "timestamp": "2025-01-15T10:30:45+00:00",
                }
            ],
            "total": 1,
        }
        response = ScreenshotListResponse(**data)
        assert response.total == 1
        assert len(response.screenshots) == 1

    def test_years_response_valid(self):
        """Test YearsResponse schema accepts valid data."""
        data = {"years": [2025, 2024, 2023]}
        response = YearsResponse(**data)
        assert response.years == [2025, 2024, 2023]

    def test_months_response_valid(self):
        """Test MonthsResponse schema accepts valid data."""
        data = {"months": [12, 11, 10]}
        response = MonthsResponse(**data)
        assert response.months == [12, 11, 10]

    def test_days_response_valid(self):
        """Test DaysResponse schema accepts valid data."""
        data = {"days": [31, 30, 29]}
        response = DaysResponse(**data)
        assert response.days == [31, 30, 29]

    def test_statistics_response_valid(self):
        """Test StatisticsResponse schema accepts valid data."""
        data = {"total": 100, "min_sta": 0.5, "max_sta": 5.0, "avg_sta": 2.5, "with_sta": 80}
        response = StatisticsResponse(**data)
        assert response.total == 100
        assert response.with_sta == 80

    def test_statistics_response_optional_fields(self):
        """Test StatisticsResponse allows optional STA fields to be None."""
        data = {"total": 0, "with_sta": 0}
        response = StatisticsResponse(**data)
        assert response.min_sta is None
        assert response.max_sta is None
        assert response.avg_sta is None


class TestApiResponseValidation:
    """Test that actual API responses conform to schemas."""

    def test_list_screenshots_response_schema(self, client):
        """Test /api/screenshot/ response conforms to schema."""
        response = client.get("/rsudp/api/screenshot/")
        assert response.status_code == 200

        data = json.loads(response.data)
        validated = ScreenshotListWithPathResponse(**data)
        assert isinstance(validated.screenshots, list)
        assert isinstance(validated.total, int)
        assert isinstance(validated.path, str)

    def test_list_years_response_schema(self, client):
        """Test /api/screenshot/years/ response conforms to schema."""
        response = client.get("/rsudp/api/screenshot/years/")
        assert response.status_code == 200

        data = json.loads(response.data)
        validated = YearsResponse(**data)
        assert isinstance(validated.years, list)

    def test_list_months_response_schema(self, client):
        """Test /api/screenshot/<year>/months/ response conforms to schema."""
        response = client.get("/rsudp/api/screenshot/2025/months/")
        assert response.status_code == 200

        data = json.loads(response.data)
        validated = MonthsResponse(**data)
        assert isinstance(validated.months, list)

    def test_list_days_response_schema(self, client):
        """Test /api/screenshot/<year>/<month>/days/ response conforms to schema."""
        response = client.get("/rsudp/api/screenshot/2025/1/days/")
        assert response.status_code == 200

        data = json.loads(response.data)
        validated = DaysResponse(**data)
        assert isinstance(validated.days, list)

    def test_list_by_date_response_schema(self, client):
        """Test /api/screenshot/<year>/<month>/<day>/ response conforms to schema."""
        response = client.get("/rsudp/api/screenshot/2025/1/15/")
        assert response.status_code == 200

        data = json.loads(response.data)
        validated = ScreenshotListResponse(**data)
        assert isinstance(validated.screenshots, list)
        assert isinstance(validated.total, int)

    def test_statistics_response_schema(self, client):
        """Test /api/screenshot/statistics/ response conforms to schema."""
        response = client.get("/rsudp/api/screenshot/statistics/")
        assert response.status_code == 200

        data = json.loads(response.data)
        validated = StatisticsResponse(**data)
        assert isinstance(validated.total, int)
        assert isinstance(validated.with_sta, int)

    def test_latest_response_schema_empty(self, client):
        """Test /api/screenshot/latest/ returns proper error when empty."""
        response = client.get("/rsudp/api/screenshot/latest/")
        if response.status_code == 404:
            data = json.loads(response.data)
            validated = ErrorResponse(**data)
            assert isinstance(validated.error, str)


class TestSchemaJsonSerialization:
    """Test that schemas serialize to JSON correctly."""

    def test_screenshot_to_json(self):
        """Test Screenshot serializes to valid JSON."""
        screenshot = Screenshot(
            filename="test.png",
            prefix="TEST",
            year=2025,
            month=1,
            day=15,
            hour=10,
            minute=30,
            second=45,
            timestamp="2025-01-15T10:30:45+00:00",
        )
        json_str = screenshot.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["filename"] == "test.png"
        assert parsed["year"] == 2025

    def test_response_to_json(self):
        """Test ScreenshotListResponse serializes to valid JSON."""
        response = ScreenshotListResponse(
            screenshots=[
                Screenshot(
                    filename="test.png",
                    prefix="TEST",
                    year=2025,
                    month=1,
                    day=15,
                    hour=10,
                    minute=30,
                    second=45,
                    timestamp="2025-01-15T10:30:45+00:00",
                )
            ],
            total=1,
        )
        json_str = response.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["total"] == 1
        assert len(parsed["screenshots"]) == 1
