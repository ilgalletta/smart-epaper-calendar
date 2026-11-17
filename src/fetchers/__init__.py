"""Data fetchers for calendar, news, weather, and commute."""

from .calendar_ics import fetch_calendar_events
from .commute import fetch_commute
from .news_ilpost import fetch_ilpost_news
from .weather import fetch_weather

__all__ = [
    "fetch_calendar_events",
    "fetch_commute",
    "fetch_ilpost_news",
    "fetch_weather",
]
