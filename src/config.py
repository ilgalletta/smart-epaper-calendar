"""Configuration loader and local JSON state manager."""

from __future__ import annotations

import copy
import json
import logging
import os
import secrets
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(
    os.environ.get(
        "EPAPER_PROJECT_ROOT",
        str(Path(__file__).resolve().parent.parent),
    )
)

DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"
DEFAULT_EXAMPLE_CONFIG_PATH = PROJECT_ROOT / "config.example.yaml"
DEFAULT_STATE_PATH = PROJECT_ROOT / "data" / "state.json"

DAYS_OF_WEEK: tuple[str, ...] = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

DEFAULT_CONFIG: dict[str, Any] = {
    "timezone": "Europe/Rome",
    "calendars": [],
    "weather": {
        "latitude": 45.4642,
        "longitude": 9.1900,
        "location_name": "Milan",
    },
    "commute": {
        "home_address": "",
        "office_address": "",
        "home_coords": None,
        "office_coords": None,
        "osrm_url": "https://router.project-osrm.org",
        "google_maps_api_key": "",
        "nominatim_user_agent": "smart-epaper-calendar/1.0",
    },
    "news": {
        "feed_url": "https://www.ilpost.it/feed/",
        "max_items": 3,
    },
    "telegram": {
        "bot_token": "",
        "allowed_chat_ids": [],
        "poll_timeout": 30,
    },
    "web_ui": {
        "host": "0.0.0.0",
        "port": 8080,
        "password": "changeme",
        "session_secret": "",
        "session_max_age_seconds": 60 * 60 * 24 * 7,
        "preview_image_path": "data/preview.png",
        "refresh_command": "",
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override into a copy of base."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def resolve_config_path(
    config_path: str | Path | None = None,
    example_path: str | Path | None = None,
) -> Path | None:
    """Return the path to config.yaml, falling back to config.example.yaml."""
    if config_path is not None:
        p = Path(config_path)
        if p.exists():
            return p

    env_path = os.environ.get("EPAPER_CONFIG_PATH")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p

    if DEFAULT_CONFIG_PATH.exists():
        return DEFAULT_CONFIG_PATH

    ex = Path(example_path) if example_path is not None else DEFAULT_EXAMPLE_CONFIG_PATH
    if ex.exists():
        return ex

    return None


def load_config(
    config_path: str | Path | None = None,
    example_path: str | Path | None = None,
) -> dict[str, Any]:
    """Load YAML configuration, falling back to config.example.yaml and defaults."""
    resolved = resolve_config_path(config_path, example_path)
    loaded: dict[str, Any] = {}
    if resolved is not None:
        try:
            with resolved.open("r", encoding="utf-8") as fh:
                raw = yaml.safe_load(fh)
            if isinstance(raw, dict):
                loaded = raw
            elif raw is not None:
                logger.warning("Config %s is not a YAML mapping; using defaults.", resolved)
        except Exception as exc:
            logger.error("Failed to read config %s: %s", resolved, exc)
    else:
        logger.info("No config.yaml or config.example.yaml found; using built-in defaults.")

    merged = _deep_merge(DEFAULT_CONFIG, loaded)
    if not merged["web_ui"].get("session_secret"):
        # Deterministic fallback per-process if not set; Web UI also persists/warns if needed.
        merged["web_ui"]["session_secret"] = os.environ.get(
            "EPAPER_SESSION_SECRET",
            secrets.token_hex(32),
        )
    return merged


def save_config(
    config: dict[str, Any],
    config_path: str | Path | None = None,
) -> Path:
    """Atomically write configuration to config.yaml."""
    target = Path(config_path) if config_path is not None else DEFAULT_CONFIG_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=".config_", suffix=".yaml.tmp", dir=str(target.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            yaml.safe_dump(config, fh, sort_keys=False, allow_unicode=True)
        os.replace(tmp_name, target)
    except Exception:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise
    return target


def _default_state() -> dict[str, Any]:
    return {
        "grocery_list": [],
        "fixed_activities": {day: [] for day in DAYS_OF_WEEK},
        "school_meals": {
            "today": "",
            "tomorrow": "",
            "updated_at": None,
        },
        "cache": {},
        "telegram": {
            "last_update_id": 0,
        },
    }


class StateManager:
    """Thread-safe local JSON state manager for data/state.json."""

    def __init__(self, state_path: str | Path | None = None) -> None:
        self.state_path = (
            Path(state_path)
            if state_path is not None
            else Path(os.environ.get("EPAPER_STATE_PATH", str(DEFAULT_STATE_PATH)))
        )
        self._lock = threading.RLock()

    def _ensure_structure(self, raw: Any) -> dict[str, Any]:
        base = _default_state()
        if not isinstance(raw, dict):
            return base
        if isinstance(raw.get("grocery_list"), list):
            base["grocery_list"] = raw["grocery_list"]
        if isinstance(raw.get("fixed_activities"), dict):
            for day in DAYS_OF_WEEK:
                items = raw["fixed_activities"].get(day, [])
                if isinstance(items, list):
                    base["fixed_activities"][day] = [str(x) for x in items if str(x).strip()]
        if isinstance(raw.get("school_meals"), dict):
            base["school_meals"]["today"] = str(raw["school_meals"].get("today", "") or "")
            base["school_meals"]["tomorrow"] = str(raw["school_meals"].get("tomorrow", "") or "")
            base["school_meals"]["updated_at"] = raw["school_meals"].get("updated_at")
        if isinstance(raw.get("cache"), dict):
            base["cache"] = raw["cache"]
        if isinstance(raw.get("telegram"), dict):
            try:
                base["telegram"]["last_update_id"] = int(
                    raw["telegram"].get("last_update_id", 0) or 0
                )
            except (TypeError, ValueError):
                base["telegram"]["last_update_id"] = 0
        return base

    def load(self) -> dict[str, Any]:
        """Load state from disk, returning normalized defaults if missing or corrupt."""
        with self._lock:
            if not self.state_path.exists():
                return _default_state()
            try:
                with self.state_path.open("r", encoding="utf-8") as fh:
                    raw = json.load(fh)
                return self._ensure_structure(raw)
            except Exception as exc:
                logger.warning("Failed to load state %s: %s", self.state_path, exc)
                return _default_state()

    def save(self, state: dict[str, Any]) -> None:
        """Atomically persist state to disk."""
        with self._lock:
            normalized = self._ensure_structure(state)
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                prefix=".state_", suffix=".json.tmp", dir=str(self.state_path.parent)
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(normalized, fh, indent=2, ensure_ascii=False)
                os.replace(tmp_name, self.state_path)
            except Exception:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
                raise

    # --- Grocery list operations ---

    def get_grocery_list(self) -> list[dict[str, Any]]:
        return self.load()["grocery_list"]

    def add_grocery_item(self, text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("Grocery item text cannot be empty")
        with self._lock:
            state = self.load()
            item = {
                "id": uuid.uuid4().hex[:8],
                "text": cleaned,
                "done": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            state["grocery_list"].append(item)
            self.save(state)
            return item

    def toggle_grocery_item(self, item_id: str) -> dict[str, Any] | None:
        with self._lock:
            state = self.load()
            for item in state["grocery_list"]:
                if item.get("id") == item_id:
                    item["done"] = not bool(item.get("done", False))
                    self.save(state)
                    return item
            return None

    def mark_grocery_done(self, identifier: str) -> dict[str, Any] | None:
        """Mark item done by 1-based index, item ID, or case-insensitive substring."""
        needle = identifier.strip()
        if not needle:
            return None
        with self._lock:
            state = self.load()
            items = state["grocery_list"]
            target: dict[str, Any] | None = None

            if needle.isdigit():
                idx = int(needle) - 1
                if 0 <= idx < len(items):
                    target = items[idx]
            if target is None:
                for item in items:
                    if item.get("id") == needle:
                        target = item
                        break
            if target is None:
                lower_needle = needle.lower()
                for item in items:
                    if not item.get("done") and lower_needle in str(item.get("text", "")).lower():
                        target = item
                        break

            if target is not None:
                target["done"] = True
                self.save(state)
            return target

    def delete_grocery_item(self, item_id: str) -> bool:
        with self._lock:
            state = self.load()
            before = len(state["grocery_list"])
            state["grocery_list"] = [
                item for item in state["grocery_list"] if item.get("id") != item_id
            ]
            changed = len(state["grocery_list"]) != before
            if changed:
                self.save(state)
            return changed

    def clear_grocery_list(self, completed_only: bool = False) -> int:
        with self._lock:
            state = self.load()
            before = len(state["grocery_list"])
            if completed_only:
                state["grocery_list"] = [
                    item for item in state["grocery_list"] if not item.get("done", False)
                ]
            else:
                state["grocery_list"] = []
            removed = before - len(state["grocery_list"])
            if removed > 0:
                self.save(state)
            return removed

    # --- Fixed weekly activities ---

    def get_fixed_activities(self) -> dict[str, list[str]]:
        return self.load()["fixed_activities"]

    def set_fixed_activities(self, activities: dict[str, list[str]]) -> dict[str, list[str]]:
        with self._lock:
            state = self.load()
            updated: dict[str, list[str]] = {}
            for day in DAYS_OF_WEEK:
                raw_items = activities.get(day, [])
                updated[day] = [str(x).strip() for x in raw_items if str(x).strip()]
            state["fixed_activities"] = updated
            self.save(state)
            return updated

    # --- School meals ---

    def get_school_meals(self) -> dict[str, Any]:
        return self.load()["school_meals"]

    def set_school_meals(self, today: str, tomorrow: str) -> dict[str, Any]:
        with self._lock:
            state = self.load()
            state["school_meals"] = {
                "today": today.strip(),
                "tomorrow": tomorrow.strip(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            self.save(state)
            return state["school_meals"]

    # --- API cache ---

    def get_cache(self, key: str, max_age_seconds: int | None = None) -> Any | None:
        state = self.load()
        entry = state["cache"].get(key)
        if not isinstance(entry, dict) or "data" not in entry:
            return None
        if max_age_seconds is not None:
            cached_at = entry.get("cached_at")
            if not cached_at:
                return None
            try:
                ts = datetime.fromisoformat(str(cached_at))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - ts).total_seconds()
                if age > max_age_seconds:
                    return None
            except ValueError:
                return None
        return entry["data"]

    def set_cache(self, key: str, data: Any) -> None:
        with self._lock:
            state = self.load()
            state["cache"][key] = {
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "data": data,
            }
            self.save(state)

    # --- Telegram offset ---

    def get_telegram_offset(self) -> int:
        return int(self.load()["telegram"].get("last_update_id", 0))

    def set_telegram_offset(self, update_id: int) -> None:
        with self._lock:
            state = self.load()
            state["telegram"]["last_update_id"] = int(update_id)
            self.save(state)
