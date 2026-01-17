#!/usr/bin/env python3
"""
気象庁の地震情報をクロールして収集する機能

Usage:
  crawl.py [-c CONFIG]

Options:
  -c CONFIG     : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
"""

import datetime
import logging
import re

import requests

import rsudp.config
import rsudp.quake.database

# JMA API endpoints
_JMA_LIST_URL = "https://www.jma.go.jp/bosai/quake/data/list.json"
_JMA_DETAIL_URL = "https://www.jma.go.jp/bosai/quake/data/{json_file}"


class InvalidCoordinateError(ValueError):
    """Invalid coordinate format error."""


def _parse_coordinate(coord_str: str) -> tuple[float, float, int]:
    """
    Parse JMA coordinate string.

    Format: "+lat+lon-depth/" (e.g., "+27.7+128.8-20000/")
    Depth is in meters, we convert to km.

    Returns:
        Tuple of (latitude, longitude, depth_km)

    """
    # Remove trailing slash
    coord_str = coord_str.rstrip("/")

    # Parse coordinates using regex
    # Format: +/-lat+/-lon-depth or +/-lat+/-lon+depth
    pattern = r"([+-][\d.]+)([+-][\d.]+)([+-]\d+)"
    match = re.match(pattern, coord_str)

    if not match:
        raise InvalidCoordinateError(coord_str)

    lat = float(match.group(1))
    lon = float(match.group(2))
    depth_m = int(match.group(3))

    # Depth is negative (below surface), convert to positive km
    depth_km = abs(depth_m) // 1000

    return lat, lon, depth_km


def _parse_intensity(intensity_str: str) -> int:
    """
    Parse JMA intensity string to numeric value.

    Returns:
        Integer representation (1-7, where 5/6 weak/strong are 50/55/60/65)

    """
    intensity_map = {
        "1": 1,
        "2": 2,
        "3": 3,
        "4": 4,
        "5-": 50,  # 震度5弱
        "5+": 55,  # 震度5強
        "6-": 60,  # 震度6弱
        "6+": 65,  # 震度6強
        "7": 7,
    }
    return intensity_map.get(intensity_str, 0)


def _parse_origin_time(origin_time_str: str) -> datetime.datetime:
    """Parse ISO format origin time string to datetime."""
    return datetime.datetime.fromisoformat(origin_time_str)


class QuakeCrawler:
    """Crawls earthquake information from JMA."""

    def __init__(self, config: rsudp.config.Config):
        """Initialize the crawler with configuration."""
        self.config = config
        self.db = rsudp.quake.database.QuakeDatabase(config)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (compatible; rsudp earthquake crawler)",
                "Accept": "application/json",
            }
        )

    def fetch_earthquake_list(self) -> list[dict]:
        """Fetch list of recent earthquakes from JMA."""
        try:
            response = self.session.get(_JMA_LIST_URL, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            logging.exception("Failed to fetch earthquake list")
            return []

    def fetch_earthquake_detail(self, json_file: str) -> dict | None:
        """Fetch detailed earthquake information."""
        try:
            url = _JMA_DETAIL_URL.format(json_file=json_file)
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            logging.exception("Failed to fetch earthquake detail: %s", json_file)
            return None

    def _process_earthquake(self, eq: dict) -> dict | None:
        """Process a single earthquake entry and store if valid."""
        max_intensity_str = eq.get("maxi", "0")
        event_id = eq.get("eid")
        json_file = eq.get("json")

        if not event_id or not json_file:
            return None

        detail = self.fetch_earthquake_detail(json_file)
        if not detail:
            return None

        try:
            earthquake_data = detail.get("Body", {}).get("Earthquake", {})
            hypocenter = earthquake_data.get("Hypocenter", {}).get("Area", {})

            origin_time_str = earthquake_data.get("OriginTime")
            if not origin_time_str:
                return None

            detected_at = _parse_origin_time(origin_time_str)

            coord_str = hypocenter.get("Coordinate", "")
            if not coord_str:
                return None

            latitude, longitude, depth = _parse_coordinate(coord_str)

            magnitude = earthquake_data.get("Magnitude", 0.0)
            if magnitude is None:
                magnitude = 0.0

            epicenter_name = hypocenter.get("Name", "不明")

            is_new = self.db.insert_earthquake(
                event_id=event_id,
                detected_at=detected_at,
                latitude=latitude,
                longitude=longitude,
                magnitude=float(magnitude),
                depth=depth,
                epicenter_name=epicenter_name,
                max_intensity=max_intensity_str,
            )

            if is_new:
                return {
                    "detected_at": detected_at,
                    "epicenter_name": epicenter_name,
                    "magnitude": float(magnitude),
                    "max_intensity": max_intensity_str,
                    "depth": depth,
                }

            return None

        except (ValueError, KeyError, TypeError):
            logging.warning("Failed to parse earthquake: %s", event_id)
            return None

    def crawl_and_store(self, min_intensity: int = 3) -> list[dict]:
        """
        Crawl earthquake data and store in database.

        Args:
            min_intensity: Minimum intensity to store (default: 3)

        Returns:
            新規追加された地震情報のリスト

        """
        earthquakes = self.fetch_earthquake_list()
        new_earthquakes = []

        for eq in earthquakes:
            max_intensity_str = eq.get("maxi", "0")
            max_intensity = _parse_intensity(max_intensity_str)

            if max_intensity < min_intensity:
                continue

            result = self._process_earthquake(eq)
            if result:
                new_earthquakes.append(result)

        return new_earthquakes


def crawl_earthquakes(config: rsudp.config.Config, min_intensity: int = 3) -> list[dict]:
    """
    Crawl and store earthquakes from JMA.

    Args:
        config: Application configuration
        min_intensity: Minimum intensity to store (default: 3)

    Returns:
        新規追加された地震情報のリスト

    """
    crawler = QuakeCrawler(config)
    return crawler.crawl_and_store(min_intensity)


######################################################################
if __name__ == "__main__":
    import pathlib

    import docopt
    import my_lib.config
    import my_lib.logger
    import my_lib.pretty

    SCHEMA_CONFIG = pathlib.Path(__file__).parent.parent.parent.parent / "schema" / "config.schema"

    assert __doc__ is not None  # noqa: S101 - type narrowing for pyright
    args = docopt.docopt(__doc__)

    my_lib.logger.init("test", level=logging.INFO)

    config_dict = my_lib.config.load(args["-c"], SCHEMA_CONFIG)
    config = rsudp.config.load_from_dict(config_dict, pathlib.Path.cwd())

    try:
        logging.info("地震情報の収集を開始します")

        # crawl_and_store で収集・保存を一括実行
        new_earthquakes = crawl_earthquakes(config, min_intensity=3)
        logging.info("新規追加: %d件", len(new_earthquakes))

        if new_earthquakes:
            logging.info(my_lib.pretty.format(new_earthquakes))

    except Exception:
        logging.exception("Error during earthquake crawl")
