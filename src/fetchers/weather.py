"""Open-Meteo weather fetcher (current + today/tomorrow forecast)."""

from __future__ import annotations

import logging
from typing import Any

import requests

from src.config import StateManager, load_config

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
CACHE_KEY = "weather"

WMO_CODES: dict[int, tuple[str, str]] = {
    0: ("Clear sky", "sun"),
    1: ("Mainly clear", "sun"),
    2: ("Partly cloudy", "partly_cloudy"),
    3: ("Overcast", "cloud"),
    45: ("Fog", "fog"),
    48: ("Depositing rime fog", "fog"),
    51: ("Light drizzle", "rain"),
    53: ("Moderate drizzle", "rain"),
    55: ("Dense drizzle", "rain"),
    56: ("Light freezing drizzle", "rain"),
    57: ("Dense freezing drizzle", "rain"),
    61: ("Slight rain", "rain"),
    63: ("Moderate rain", "rain"),
    65: ("Heavy rain", "rain"),
    66: ("Light freezing rain", "rain"),
    67: ("Heavy freezing rain", "rain"),
    71: ("Slight snow", "snow"),
    73: ("Moderate snow", "snow"),
    75: ("Heavy snow", "snow"),
    77: ("Snow grains", "snow"),
    80: ("Slight rain showers", "rain"),
    81: ("Moderate rain showers", "rain"),
    82: ("Violent rain showers", "rain"),
    85: ("Slight snow showers", "snow"),
    86: ("Heavy snow showers", "snow"),
    95: ("Thunderstorm", "storm"),
    96: ("Thunderstorm with slight hail", "storm"),
    99: ("Thunderstorm with heavy hail", "storm"),
}


def describe_wmo_code(code: int | None) -> tuple[str, str]:
    """Return (description, icon_key) for a WMO weather code."""
    if code is None:
        return ("Unknown", "cloud")
    return WMO_CODES.get(int(code), ("Cloudy", "cloud"))


def _safe_index(values: list[Any], idx: int) -> Any:
    return values[idx] if isinstance(values, list) and 0 <= idx < len(values) else None


def fetch_weather(
    config: dict[str, Any] | None = None,
    state_manager: StateManager | None = None,
    timeout: int = 12,
) -> dict[str, Any]:
    """Fetch current + today/tomorrow forecast from Open-Meteo with cache fallback."""
    cfg = config if config is not None else load_config()
    sm = state_manager if state_manager is not None else StateManager()

    weather_cfg = cfg.get("weather", {}) if isinstance(cfg.get("weather"), dict) else {}
    lat = float(weather_cfg.get("latitude", 45.4642))
    lon = float(weather_cfg.get("longitude", 9.1900))
    location_name = str(weather_cfg.get("location_name", ""))
    tz_name = str(cfg.get("timezone", "Europe/Rome"))

    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
        "forecast_days": 2,
        "timezone": tz_name,
    }

    try:
        resp = requests.get(OPEN_METEO_URL, params=params, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()

        current_raw = payload.get("current", {})
        cur_code = current_raw.get("weather_code")
        cur_desc, cur_icon = describe_wmo_code(cur_code)

        daily_raw = payload.get("daily", {})
        dates = daily_raw.get("time", [])
        codes = daily_raw.get("weather_code", [])
        tmax = daily_raw.get("temperature_2m_max", [])
        tmin = daily_raw.get("temperature_2m_min", [])
        precip = daily_raw.get("precipitation_probability_max", [])
        sunrise = daily_raw.get("sunrise", [])
        sunset = daily_raw.get("sunset", [])

        daily_forecast: list[dict[str, Any]] = []
        for idx in range(min(2, len(dates))):
            d_code = _safe_index(codes, idx)
            d_desc, d_icon = describe_wmo_code(d_code)
            daily_forecast.append(
                {
                    "date": _safe_index(dates, idx),
                    "weather_code": d_code,
                    "description": d_desc,
                    "icon": d_icon,
                    "temp_max": _safe_index(tmax, idx),
                    "temp_min": _safe_index(tmin, idx),
                    "precip_prob_max": _safe_index(precip, idx),
                    "sunrise": _safe_index(sunrise, idx),
                    "sunset": _safe_index(sunset, idx),
                }
            )

        result: dict[str, Any] = {
            "location": location_name,
            "latitude": lat,
            "longitude": lon,
            "current": {
                "temperature": current_raw.get("temperature_2m"),
                "apparent_temperature": current_raw.get("apparent_temperature"),
                "humidity": current_raw.get("relative_humidity_2m"),
                "wind_speed": current_raw.get("wind_speed_10m"),
                "weather_code": cur_code,
                "description": cur_desc,
                "icon": cur_icon,
            },
            "today": daily_forecast[0] if len(daily_forecast) > 0 else {},
            "tomorrow": daily_forecast[1] if len(daily_forecast) > 1 else {},
        }
        sm.set_cache(CACHE_KEY, result)
        return result
    except Exception as exc:
        logger.warning("Failed to fetch Open-Meteo weather: %s", exc)

    cached = sm.get_cache(CACHE_KEY)
    if isinstance(cached, dict):
        logger.info("Using cached weather data.")
        return cached
    return {
        "location": location_name,
        "latitude": lat,
        "longitude": lon,
        "current": {},
        "today": {},
        "tomorrow": {},
    }
