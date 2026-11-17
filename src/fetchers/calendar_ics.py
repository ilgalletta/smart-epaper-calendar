"""Google Calendar / iCal (.ics) fetcher with recurring event expansion and cache fallback."""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import icalendar
import recurring_ical_events
import requests

from src.config import StateManager, load_config

logger = logging.getLogger(__name__)

CACHE_KEY = "calendar_ics"


def _normalize_calendar_entries(raw_calendars: Any) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    if not isinstance(raw_calendars, list):
        return entries
    for idx, item in enumerate(raw_calendars):
        if isinstance(item, str) and item.strip():
            entries.append({"name": f"Calendar {idx + 1}", "url": item.strip()})
        elif isinstance(item, dict) and str(item.get("url", "")).strip():
            entries.append(
                {
                    "name": str(item.get("name") or f"Calendar {idx + 1}").strip(),
                    "url": str(item["url"]).strip(),
                }
            )
    return entries


def _to_local_datetime(value: date | datetime, tz: ZoneInfo) -> tuple[datetime, bool]:
    """Return (localized_datetime, is_all_day)."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=tz), False
        return value.astimezone(tz), False
    return datetime.combine(value, time.min, tzinfo=tz), True


def parse_ics_events(
    ics_bytes: bytes,
    calendar_name: str,
    start_date: date,
    days: int,
    tz: ZoneInfo,
) -> list[dict[str, Any]]:
    """Parse an ICS payload and expand recurring events within [start_date, start_date + days)."""
    cal = icalendar.Calendar.from_ical(ics_bytes)
    window_start = datetime.combine(start_date, time.min, tzinfo=tz)
    window_end = window_start + timedelta(days=days)

    expanded = recurring_ical_events.of(cal).between(window_start, window_end)
    parsed: list[dict[str, Any]] = []

    for component in expanded:
        dtstart_prop = component.get("DTSTART")
        if dtstart_prop is None:
            continue
        dtstart_raw = dtstart_prop.dt
        start_dt, all_day = _to_local_datetime(dtstart_raw, tz)

        dtend_prop = component.get("DTEND")
        if dtend_prop is not None:
            end_dt, _ = _to_local_datetime(dtend_prop.dt, tz)
        else:
            end_dt = start_dt + (timedelta(days=1) if all_day else timedelta(hours=1))

        summary = str(component.get("SUMMARY", "(No title)") or "(No title)").strip()
        location = str(component.get("LOCATION", "") or "").strip()

        # An all-day or multi-day event may span multiple dates in the 7-day window.
        if all_day:
            first_day = max(start_dt.date(), start_date)
            last_day_exclusive = min(end_dt.date(), start_date + timedelta(days=days))
            if last_day_exclusive <= first_day:
                last_day_exclusive = first_day + timedelta(days=1)
            cur = first_day
            while cur < last_day_exclusive:
                parsed.append(
                    {
                        "date": cur.isoformat(),
                        "summary": summary,
                        "location": location,
                        "calendar": calendar_name,
                        "all_day": True,
                        "start_time": None,
                        "end_time": None,
                        "start_iso": start_dt.isoformat(),
                    }
                )
                cur += timedelta(days=1)
        else:
            event_date = start_dt.date()
            if start_date <= event_date < start_date + timedelta(days=days):
                parsed.append(
                    {
                        "date": event_date.isoformat(),
                        "summary": summary,
                        "location": location,
                        "calendar": calendar_name,
                        "all_day": False,
                        "start_time": start_dt.strftime("%H:%M"),
                        "end_time": end_dt.strftime("%H:%M"),
                        "start_iso": start_dt.isoformat(),
                    }
                )

    return parsed


def fetch_calendar_events(
    config: dict[str, Any] | None = None,
    state_manager: StateManager | None = None,
    days: int = 7,
    timeout: int = 15,
) -> dict[str, list[dict[str, Any]]]:
    """Fetch events for the next `days` days grouped by YYYY-MM-DD, with cache fallback."""
    cfg = config if config is not None else load_config()
    sm = state_manager if state_manager is not None else StateManager()

    tz_name = str(cfg.get("timezone", "Europe/Rome"))
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        logger.warning("Invalid timezone %r; falling back to UTC", tz_name)
        tz = ZoneInfo("UTC")

    today = datetime.now(tz).date()
    grouped: dict[str, list[dict[str, Any]]] = {
        (today + timedelta(days=offset)).isoformat(): [] for offset in range(days)
    }

    entries = _normalize_calendar_entries(cfg.get("calendars", []))
    if not entries:
        return grouped

    all_events: list[dict[str, Any]] = []
    any_success = False

    for entry in entries:
        url = entry["url"]
        name = entry["name"]
        try:
            resp = requests.get(
                url,
                timeout=timeout,
                headers={"User-Agent": "smart-epaper-calendar/1.0"},
            )
            resp.raise_for_status()
            events = parse_ics_events(resp.content, name, today, days, tz)
            all_events.extend(events)
            any_success = True
        except Exception as exc:
            logger.warning("Failed to fetch/parse calendar %r (%s): %s", name, url, exc)

    if not any_success:
        cached = sm.get_cache(CACHE_KEY)
        if isinstance(cached, dict):
            logger.info("Using cached calendar events due to fetch failure.")
            return cached
        return grouped

    for ev in all_events:
        day_key = ev["date"]
        if day_key in grouped:
            grouped[day_key].append(ev)

    for day_key in grouped:
        grouped[day_key].sort(
            key=lambda e: (0 if e["all_day"] else 1, e.get("start_time") or "")
        )

    sm.set_cache(CACHE_KEY, grouped)
    return grouped
