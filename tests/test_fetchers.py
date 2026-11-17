"""Unit tests for all fetchers in src/fetchers/."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
import requests

from src.config import StateManager
from src.fetchers.calendar_ics import fetch_calendar_events, parse_ics_events
from src.fetchers.commute import _parse_coords, fetch_commute
from src.fetchers.news_ilpost import fetch_ilpost_news
from src.fetchers.weather import describe_wmo_code, fetch_weather


def _make_sample_ics(base_date: date) -> bytes:
    d0 = base_date.strftime("%Y%m%d")
    d1 = (base_date + timedelta(days=1)).strftime("%Y%m%d")
    d2 = (base_date + timedelta(days=2)).strftime("%Y%m%d")
    d4 = (base_date + timedelta(days=4)).strftime("%Y%m%d")
    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//Test//Smart E-Paper Calendar//EN\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:timed-1@test\r\n"
        f"DTSTART;TZID=Europe/Rome:{d0}T093000\r\n"
        f"DTEND;TZID=Europe/Rome:{d0}T103000\r\n"
        "SUMMARY:Standup Ingegneria\r\n"
        "LOCATION:Sala A\r\n"
        "END:VEVENT\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:allday-multi@test\r\n"
        f"DTSTART;VALUE=DATE:{d1}\r\n"
        f"DTEND;VALUE=DATE:{d2}\r\n"
        "SUMMARY:Gita Scolastica\r\n"
        "END:VEVENT\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:recurring-1@test\r\n"
        f"DTSTART;TZID=Europe/Rome:{d0}T180000\r\n"
        f"DTEND;TZID=Europe/Rome:{d0}T190000\r\n"
        "RRULE:FREQ=DAILY;COUNT=3\r\n"
        "SUMMARY:Allenamento\r\n"
        "END:VEVENT\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:utc-1@test\r\n"
        f"DTSTART:{d4}T080000Z\r\n"
        f"DTEND:{d4}T090000Z\r\n"
        "SUMMARY:Call UTC\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    ).encode("utf-8")


def test_parse_ics_events_timed_allday_and_recurring() -> None:
    tz = ZoneInfo("Europe/Rome")
    start = date(2026, 5, 11)
    ics_bytes = _make_sample_ics(start)

    events = parse_ics_events(ics_bytes, "Family", start, days=7, tz=tz)
    summaries = [e["summary"] for e in events]

    assert "Standup Ingegneria" in summaries
    assert "Gita Scolastica" in summaries
    assert summaries.count("Allenamento") == 3
    assert "Call UTC" in summaries

    all_day_ev = next(e for e in events if e["summary"] == "Gita Scolastica")
    assert all_day_ev["all_day"] is True
    assert all_day_ev["start_time"] is None
    assert all_day_ev["date"] == "2026-05-12"

    timed_ev = next(e for e in events if e["summary"] == "Standup Ingegneria")
    assert timed_ev["all_day"] is False
    assert timed_ev["start_time"] == "09:30"
    assert timed_ev["end_time"] == "10:30"
    assert timed_ev["location"] == "Sala A"


def test_fetch_calendar_events_with_mock_and_cache_fallback(
    state_manager: StateManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tz = ZoneInfo("Europe/Rome")
    today = datetime.now(tz).date()
    ics_bytes = _make_sample_ics(today)

    mock_resp = MagicMock()
    mock_resp.content = ics_bytes
    mock_resp.raise_for_status.return_value = None
    monkeypatch.setattr("src.fetchers.calendar_ics.requests.get", lambda *a, **kw: mock_resp)

    cfg = {
        "timezone": "Europe/Rome",
        "calendars": [{"name": "Family", "url": "https://example.com/cal.ics"}],
    }
    grouped = fetch_calendar_events(config=cfg, state_manager=state_manager, days=7)
    assert len(grouped) == 7
    assert any(ev["summary"] == "Standup Ingegneria" for ev in grouped[today.isoformat()])

    # Simulate network failure -> should return cached data
    def _fail(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr("src.fetchers.calendar_ics.requests.get", _fail)
    cached_grouped = fetch_calendar_events(config=cfg, state_manager=state_manager, days=7)
    assert cached_grouped == grouped


def test_fetch_ilpost_news_and_cache_fallback(
    state_manager: StateManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rss_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel><title>Il Post</title>
      <item><title>Titolo &amp; <b>Uno</b></title><link>https://ilpost.it/1</link><description>&lt;p&gt;Testo 1&lt;/p&gt;</description></item>
      <item><title>Titolo Due</title><link>https://ilpost.it/2</link><description>Testo 2</description></item>
      <item><title>Titolo Tre</title><link>https://ilpost.it/3</link><description>Testo 3</description></item>
      <item><title>Titolo Quattro</title><link>https://ilpost.it/4</link><description>Testo 4</description></item>
    </channel></rss>"""

    mock_resp = MagicMock()
    mock_resp.content = rss_xml
    mock_resp.raise_for_status.return_value = None
    monkeypatch.setattr("src.fetchers.news_ilpost.requests.get", lambda *a, **kw: mock_resp)

    cfg = {"news": {"feed_url": "https://www.ilpost.it/feed/", "max_items": 3}}
    items = fetch_ilpost_news(config=cfg, state_manager=state_manager)
    assert len(items) == 3
    assert items[0]["title"] == "Titolo & Uno"
    assert items[0]["summary"] == "Testo 1"

    def _fail(*args, **kwargs):
        raise requests.Timeout("timeout")

    monkeypatch.setattr("src.fetchers.news_ilpost.requests.get", _fail)
    cached = fetch_ilpost_news(config=cfg, state_manager=state_manager)
    assert cached == items


def test_fetch_weather_and_wmo_codes(
    state_manager: StateManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert describe_wmo_code(0) == ("Clear sky", "sun")
    assert describe_wmo_code(None) == ("Unknown", "cloud")

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {
        "current": {
            "temperature_2m": 14.5,
            "apparent_temperature": 13.0,
            "relative_humidity_2m": 60,
            "wind_speed_10m": 8.2,
            "weather_code": 2,
        },
        "daily": {
            "time": ["2026-05-11", "2026-05-12"],
            "weather_code": [2, 61],
            "temperature_2m_max": [18.0, 15.0],
            "temperature_2m_min": [9.0, 8.0],
            "precipitation_probability_max": [10, 80],
            "sunrise": ["05:50", "05:49"],
            "sunset": ["20:40", "20:41"],
        },
    }
    monkeypatch.setattr("src.fetchers.weather.requests.get", lambda *a, **kw: mock_resp)

    cfg = {"timezone": "Europe/Rome", "weather": {"latitude": 45.46, "longitude": 9.19, "location_name": "Milano"}}
    res = fetch_weather(config=cfg, state_manager=state_manager)
    assert res["location"] == "Milano"
    assert res["current"]["temperature"] == 14.5
    assert res["current"]["icon"] == "partly_cloudy"
    assert res["today"]["temp_max"] == 18.0
    assert res["tomorrow"]["icon"] == "rain"

    def _fail(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr("src.fetchers.weather.requests.get", _fail)
    assert fetch_weather(config=cfg, state_manager=state_manager) == res


def test_commute_osrm_geocoding_and_fallbacks(
    state_manager: StateManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _parse_coords([45.46, 9.19]) == (45.46, 9.19)
    assert _parse_coords({"lat": "45.47", "lon": "9.18"}) == (45.47, 9.18)
    assert _parse_coords("invalid") is None

    def _fake_get(url, params=None, headers=None, timeout=10):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        if "nominatim" in url:
            q = params["q"]
            if "Home" in q:
                resp.json.return_value = [{"lat": "45.4642", "lon": "9.1900"}]
            else:
                resp.json.return_value = [{"lat": "45.4773", "lon": "9.1815"}]
        elif "route/v1/driving" in url:
            resp.json.return_value = {
                "code": "Ok",
                "routes": [{"duration": 1440, "distance": 8500}],
            }
        return resp

    monkeypatch.setattr("src.fetchers.commute.requests.get", _fake_get)
    cfg = {
        "commute": {
            "home_address": "Home Street 1",
            "office_address": "Office Piazza 2",
        }
    }
    res = fetch_commute(config=cfg, state_manager=state_manager)
    assert res["provider"] == "osrm"
    assert res["duration_minutes"] == 24
    assert res["distance_km"] == 8.5

    # Unconfigured commute with empty cache returns provider=none
    empty_sm = StateManager(state_path=state_manager.state_path.parent / "empty_state.json")
    none_res = fetch_commute(config={"commute": {}}, state_manager=empty_sm)
    assert none_res["provider"] == "none"
    assert none_res["duration_minutes"] is None
