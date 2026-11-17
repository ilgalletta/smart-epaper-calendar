"""Morning commute travel-time fetcher (Google Maps Distance Matrix + OSRM fallback)."""

from __future__ import annotations

import logging
from typing import Any

import requests

from src.config import StateManager, load_config

logger = logging.getLogger(__name__)

GOOGLE_DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"
NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
DEFAULT_OSRM_URL = "https://router.project-osrm.org"
CACHE_KEY = "commute"
GEOCODE_CACHE_PREFIX = "geocode:"


def _parse_coords(raw: Any) -> tuple[float, float] | None:
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        try:
            return (float(raw[0]), float(raw[1]))
        except (TypeError, ValueError):
            return None
    if isinstance(raw, dict) and "lat" in raw and "lon" in raw:
        try:
            return (float(raw["lat"]), float(raw["lon"]))
        except (TypeError, ValueError):
            return None
    return None


def _geocode_address(
    address: str,
    sm: StateManager,
    user_agent: str,
    timeout: int = 10,
) -> tuple[float, float] | None:
    addr = address.strip()
    if not addr:
        return None

    cache_key = f"{GEOCODE_CACHE_PREFIX}{addr.lower()}"
    cached = sm.get_cache(cache_key)
    coords = _parse_coords(cached)
    if coords is not None:
        return coords

    try:
        resp = requests.get(
            NOMINATIM_SEARCH_URL,
            params={"q": addr, "format": "json", "limit": 1},
            headers={"User-Agent": user_agent},
            timeout=timeout,
        )
        resp.raise_for_status()
        results = resp.json()
        if isinstance(results, list) and results:
            lat = float(results[0]["lat"])
            lon = float(results[0]["lon"])
            sm.set_cache(cache_key, {"lat": lat, "lon": lon})
            return (lat, lon)
    except Exception as exc:
        logger.warning("Nominatim geocoding failed for %r: %s", addr, exc)
    return None


def _fetch_google_maps(
    home: str,
    office: str,
    api_key: str,
    timeout: int = 12,
) -> dict[str, Any] | None:
    params = {
        "origins": home,
        "destinations": office,
        "mode": "driving",
        "departure_time": "now",
        "key": api_key,
    }
    resp = requests.get(GOOGLE_DISTANCE_MATRIX_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "OK":
        raise RuntimeError(f"Google Maps API status: {data.get('status')}")

    element = data["rows"][0]["elements"][0]
    if element.get("status") != "OK":
        raise RuntimeError(f"Google Maps element status: {element.get('status')}")

    dur = element.get("duration_in_traffic") or element.get("duration") or {}
    dist = element.get("distance") or {}
    seconds = int(dur.get("value", 0))
    meters = int(dist.get("value", 0))
    return {
        "provider": "google_maps",
        "duration_minutes": max(1, round(seconds / 60)),
        "duration_text": dur.get("text") or f"{max(1, round(seconds / 60))} min",
        "distance_km": round(meters / 1000, 1),
        "origin": home,
        "destination": office,
    }


def _fetch_osrm(
    home_coords: tuple[float, float],
    office_coords: tuple[float, float],
    osrm_base_url: str,
    home_label: str,
    office_label: str,
    timeout: int = 12,
) -> dict[str, Any]:
    base = osrm_base_url.rstrip("/")
    # OSRM expects lon,lat;lon,lat
    coords_str = (
        f"{home_coords[1]},{home_coords[0]};{office_coords[1]},{office_coords[0]}"
    )
    url = f"{base}/route/v1/driving/{coords_str}"
    resp = requests.get(url, params={"overview": "false"}, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        raise RuntimeError(f"OSRM error: {data.get('code')}")

    route = data["routes"][0]
    seconds = float(route.get("duration", 0))
    meters = float(route.get("distance", 0))
    minutes = max(1, round(seconds / 60))
    return {
        "provider": "osrm",
        "duration_minutes": minutes,
        "duration_text": f"{minutes} min",
        "distance_km": round(meters / 1000, 1),
        "origin": home_label,
        "destination": office_label,
    }


def fetch_commute(
    config: dict[str, Any] | None = None,
    state_manager: StateManager | None = None,
    timeout: int = 12,
) -> dict[str, Any]:
    """Calculate commute duration between Home and Office with Google Maps / OSRM & cache fallback."""
    cfg = config if config is not None else load_config()
    sm = state_manager if state_manager is not None else StateManager()

    commute_cfg = cfg.get("commute", {}) if isinstance(cfg.get("commute"), dict) else {}
    home_address = str(commute_cfg.get("home_address", "") or "").strip()
    office_address = str(commute_cfg.get("office_address", "") or "").strip()
    api_key = str(commute_cfg.get("google_maps_api_key", "") or "").strip()
    osrm_url = str(commute_cfg.get("osrm_url") or DEFAULT_OSRM_URL).strip()
    user_agent = str(
        commute_cfg.get("nominatim_user_agent") or "smart-epaper-calendar/1.0"
    )

    home_coords = _parse_coords(commute_cfg.get("home_coords"))
    office_coords = _parse_coords(commute_cfg.get("office_coords"))

    # 1. Try Google Maps Distance Matrix if API key and addresses/coords are present
    if api_key:
        origin = home_address or (f"{home_coords[0]},{home_coords[1]}" if home_coords else "")
        dest = office_address or (f"{office_coords[0]},{office_coords[1]}" if office_coords else "")
        if origin and dest:
            try:
                result = _fetch_google_maps(origin, dest, api_key, timeout=timeout)
                if result:
                    sm.set_cache(CACHE_KEY, result)
                    return result
            except Exception as exc:
                logger.warning("Google Maps commute fetch failed, falling back to OSRM: %s", exc)

    # 2. Try OSRM (geocoding via Nominatim if coordinates aren't configured)
    if home_coords is None and home_address:
        home_coords = _geocode_address(home_address, sm, user_agent, timeout=timeout)
    if office_coords is None and office_address:
        office_coords = _geocode_address(office_address, sm, user_agent, timeout=timeout)

    if home_coords is not None and office_coords is not None:
        try:
            result = _fetch_osrm(
                home_coords,
                office_coords,
                osrm_url,
                home_address or f"{home_coords[0]},{home_coords[1]}",
                office_address or f"{office_coords[0]},{office_coords[1]}",
                timeout=timeout,
            )
            sm.set_cache(CACHE_KEY, result)
            return result
        except Exception as exc:
            logger.warning("OSRM commute fetch failed: %s", exc)

    # 3. Fallback to cached commute data
    cached = sm.get_cache(CACHE_KEY)
    if isinstance(cached, dict):
        logger.info("Using cached commute data.")
        return cached

    return {
        "provider": "none",
        "duration_minutes": None,
        "duration_text": "N/A",
        "distance_km": None,
        "origin": home_address,
        "destination": office_address,
    }
