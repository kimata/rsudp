# ruff: noqa: S101
"""
API schema consistency tests between frontend (TypeScript) and backend (Python).

This module verifies that:
1. Pydantic schemas match the TypeScript interfaces in frontend/src/types.ts
2. API responses conform to the defined schemas
"""

import json
import re
from pathlib import Path
from typing import Any, get_args, get_origin

import pytest
from pydantic import BaseModel, ValidationError

from rsudp.webui.api.schemas import (
    Earthquake,
    ErrorResponse,
    Screenshot,
    ScreenshotListResponse,
    ScreenshotListWithPathResponse,
    StatisticsResponse,
    SysInfo,
)


class TestSchemaFieldConsistency:
    """Test that Pydantic schemas match TypeScript interfaces."""

    @pytest.fixture
    def typescript_types(self) -> dict[str, dict[str, Any]]:
        """Parse TypeScript interfaces from frontend/src/types.ts."""
        types_file = Path(__file__).parent.parent / "frontend" / "src" / "types.ts"
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
            "Earthquake": {Earthquake},
        }
        return type_mapping.get(ts_type, {object})

    def _get_pydantic_field_type(self, model: type[BaseModel], field_name: str) -> tuple[type, bool]:
        """Get the type and optionality of a Pydantic model field."""
        import types

        field_info = model.model_fields.get(field_name)
        if field_info is None:
            raise ValueError(f"Field {field_name} not found in {model.__name__}")

        annotation = field_info.annotation
        is_optional = False
        actual_type = annotation

        origin = get_origin(annotation)

        # Handle Union types (including X | None syntax)
        if origin is types.UnionType or (origin is not None and str(origin) == "typing.Union"):
            args = get_args(annotation)
            # Check if None is one of the union members (optional field)
            if type(None) in args:
                is_optional = True
                # Get the non-None type
                for arg in args:
                    if arg is not type(None):
                        actual_type = arg
                        break
            else:
                actual_type = args[0] if args else object

        if origin is list or str(actual_type).startswith("list"):
            return list, is_optional

        if actual_type in (int, float, str, bool):
            return actual_type, is_optional

        # Handle class types (like Earthquake)
        if isinstance(actual_type, type):
            return actual_type, is_optional

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

    def test_earthquake_schema_matches_typescript(self, typescript_types):
        """Verify Earthquake schema matches TypeScript interface."""
        ts_earthquake = typescript_types.get("Earthquake")
        assert ts_earthquake is not None, "Earthquake interface not found in TypeScript"

        for field_name in ts_earthquake:
            assert field_name in Earthquake.model_fields, (
                f"Field '{field_name}' missing in Pydantic Earthquake"
            )


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
            "max_count": 1000.0,
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
            "max_count": 1000.0,
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
            "max_count": 1000.0,
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
                    "max_count": 1000.0,
                }
            ],
            "total": 1,
        }
        response = ScreenshotListResponse(**data)
        assert response.total == 1
        assert len(response.screenshots) == 1

    def test_statistics_response_valid(self):
        """Test StatisticsResponse schema accepts valid data."""
        data = {
            "total": 100,
            "absolute_total": 150,
            "min_signal": 0.5,
            "max_signal": 5.0,
            "avg_signal": 2.5,
            "with_signal": 80,
            "earthquake_count": 5,
        }
        response = StatisticsResponse(**data)
        assert response.total == 100
        assert response.with_signal == 80

    def test_statistics_response_optional_fields(self):
        """Test StatisticsResponse allows optional fields to be None."""
        data = {"total": 0, "absolute_total": 0, "with_signal": 0}
        response = StatisticsResponse(**data)
        assert response.min_signal is None
        assert response.max_signal is None
        assert response.avg_signal is None


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

    def test_statistics_response_schema(self, client):
        """Test /api/screenshot/statistics/ response conforms to schema."""
        response = client.get("/rsudp/api/screenshot/statistics/")
        assert response.status_code == 200

        data = json.loads(response.data)
        validated = StatisticsResponse(**data)
        assert isinstance(validated.total, int)
        assert isinstance(validated.with_signal, int)

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
            max_count=1000.0,
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
                    max_count=1000.0,
                )
            ],
            total=1,
        )
        json_str = response.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["total"] == 1
        assert len(parsed["screenshots"]) == 1
