"""ilPost.it RSS feed fetcher."""

from __future__ import annotations

import html
import logging
import re
from typing import Any

import feedparser
import requests

from src.config import StateManager, load_config

logger = logging.getLogger(__name__)

DEFAULT_FEED_URL = "https://www.ilpost.it/feed/"
CACHE_KEY = "news_ilpost"
_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(raw: str) -> str:
    text = _TAG_RE.sub("", raw or "")
    text = html.unescape(text)
    return " ".join(text.split())


def fetch_ilpost_news(
    config: dict[str, Any] | None = None,
    state_manager: StateManager | None = None,
    timeout: int = 12,
) -> list[dict[str, str]]:
    """Fetch top N headlines (default 3) from ilPost.it RSS feed with cache fallback."""
    cfg = config if config is not None else load_config()
    sm = state_manager if state_manager is not None else StateManager()

    news_cfg = cfg.get("news", {}) if isinstance(cfg.get("news"), dict) else {}
    feed_url = str(news_cfg.get("feed_url") or DEFAULT_FEED_URL)
    max_items = int(news_cfg.get("max_items") or 3)

    try:
        resp = requests.get(
            feed_url,
            timeout=timeout,
            headers={"User-Agent": "smart-epaper-calendar/1.0"},
        )
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)
        entries = getattr(parsed, "entries", []) or []

        headlines: list[dict[str, str]] = []
        for entry in entries[:max_items]:
            title = _clean_text(str(entry.get("title", "")))
            if not title:
                continue
            headlines.append(
                {
                    "title": title,
                    "link": str(entry.get("link", "")).strip(),
                    "published": str(entry.get("published", "")).strip(),
                    "summary": _clean_text(str(entry.get("summary", "")))[:200],
                }
            )

        if headlines:
            sm.set_cache(CACHE_KEY, headlines)
            return headlines
    except Exception as exc:
        logger.warning("Failed to fetch ilPost.it feed (%s): %s", feed_url, exc)

    cached = sm.get_cache(CACHE_KEY)
    if isinstance(cached, list):
        logger.info("Using cached ilPost.it headlines.")
        return cached
    return []
