"""
Smart E-Paper Calendar Orchestrator (src/main.py).

Coordinates configuration & state loading, one-shot Telegram grocery polling,
data fetching (Google Calendar .ics, ilPost.it RSS, Open-Meteo weather, commute),
3-color e-Paper rendering via ``epaper_ui.py``, and hardware/mock display updates.

Supports:
  - ``--sync-once``: Battery / Witty Pi wake-sync-shutdown cycle.
  - ``--web``: Keeps the LAN FastAPI Web UI running on the configured host/port.
  - ``--mock``: Forces Mock/Simulation display mode (saves ``data/preview.png``).
"""

from __future__ import annotations

import argparse
import importlib
import logging
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from src.config import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_STATE_PATH,
    StateManager,
    load_config,
)
from src.display.waveshare_7in5_b import EPD_HEIGHT, EPD_WIDTH, Waveshare7in5B
from src.fetchers.calendar_ics import fetch_calendar_events
from src.fetchers.commute import fetch_commute
from src.fetchers.news_ilpost import fetch_ilpost_news
from src.fetchers.school_menu_milano import resolve_school_menu
from src.fetchers.weather import fetch_weather
from src.renderer.epaper_ui import render_dashboard
from src.telegram_bot import GroceryTelegramBot

logger = logging.getLogger("smart_calendar.main")

_ITALIAN_DAY_ABBR = {
    "Monday": "LUN",
    "Tuesday": "MAR",
    "Wednesday": "MER",
    "Thursday": "GIO",
    "Friday": "VEN",
    "Saturday": "SAB",
    "Sunday": "DOM",
}


def _resolve_timezone(cfg: dict[str, Any]) -> ZoneInfo:
    tz_name = str(
        cfg.get("timezone")
        or (cfg.get("general", {}) if isinstance(cfg.get("general"), dict) else {}).get(
            "timezone", "Europe/Rome"
        )
        or "Europe/Rome"
    )
    try:
        return ZoneInfo(tz_name)
    except Exception:
        logger.warning("Invalid timezone %r; falling back to UTC.", tz_name)
        return ZoneInfo("UTC")


def _adapt_calendar_days(
    grouped_events: dict[str, list[dict[str, Any]]],
    now: datetime,
) -> list[dict[str, Any]]:
    """Convert grouped calendar_ics output into epaper_ui's ``calendar_days`` format."""
    today = now.date()
    monday = today - timedelta(days=today.weekday())
    calendar_days: list[dict[str, Any]] = []

    for offset in range(7):
        day_iso = (monday + timedelta(days=offset)).isoformat()
        raw_events = grouped_events.get(day_iso, [])
        formatted_events: list[dict[str, Any]] = []
        for ev in raw_events:
            formatted_events.append(
                {
                    "time": "" if ev.get("all_day") else str(ev.get("start_time") or ""),
                    "title": str(ev.get("summary") or "(Senza titolo)"),
                    "important": bool(ev.get("important", False)),
                }
            )
        calendar_days.append({"date": day_iso, "events": formatted_events})

    return calendar_days


def _adapt_fixed_activities(raw_activities: Any) -> list[dict[str, str]]:
    """Convert state/config fixed_activities into epaper_ui's list format."""
    adapted: list[dict[str, str]] = []
    if isinstance(raw_activities, list):
        for item in raw_activities:
            if isinstance(item, dict):
                adapted.append(
                    {
                        "days": str(item.get("days", "")),
                        "time": str(item.get("time", "")),
                        "title": str(item.get("title", "")),
                    }
                )
        return adapted

    if isinstance(raw_activities, dict):
        for day_name, items in raw_activities.items():
            abbr = _ITALIAN_DAY_ABBR.get(str(day_name), str(day_name)[:3].upper())
            if not isinstance(items, list):
                continue
            for entry in items:
                if isinstance(entry, dict):
                    adapted.append(
                        {
                            "days": abbr,
                            "time": str(entry.get("time", "")),
                            "title": str(entry.get("title", "")),
                        }
                    )
                elif str(entry).strip():
                    adapted.append({"days": abbr, "time": "", "title": str(entry).strip()})
    return adapted


def _adapt_school_meals(
    state_meals: dict[str, Any],
    cfg: dict[str, Any],
    now: datetime,
    state_manager: Optional[StateManager] = None,
) -> dict[str, Any]:
    """Build ``mensa`` payload via ``resolve_school_menu`` (state, milanoristorazione.it, config.yaml)."""
    return resolve_school_menu(state_meals, cfg, now, state_manager=state_manager)


def _adapt_weather(raw_weather: dict[str, Any]) -> dict[str, Any]:
    current = raw_weather.get("current", {}) if isinstance(raw_weather.get("current"), dict) else {}
    today = raw_weather.get("today", {}) if isinstance(raw_weather.get("today"), dict) else {}
    temp = current.get("temperature")
    tmin = today.get("temp_min")
    tmax = today.get("temp_max")
    return {
        "city": str(raw_weather.get("location") or "Home"),
        "temp": temp if temp is not None else "--",
        "temp_min": tmin if tmin is not None else "--",
        "temp_max": tmax if tmax is not None else "--",
        "condition": str(current.get("description") or "N/D"),
        "icon": str(current.get("icon") or "cloud"),
    }


def _adapt_commute(raw_commute: dict[str, Any]) -> dict[str, Any]:
    duration = raw_commute.get("duration_minutes")
    dest = str(raw_commute.get("destination") or "").strip()
    provider = str(raw_commute.get("provider") or "").upper()
    return {
        "duration_min": duration if duration is not None else "--",
        "traffic_status": "REGOLARE" if duration is not None else "N/D",
        "route": dest or (provider if provider != "NONE" else "Casa -> Ufficio"),
        "eta_note": str(raw_commute.get("duration_text") or ""),
    }


def _adapt_grocery(raw_grocery: list[dict[str, Any]]) -> list[Any]:
    items: list[Any] = []
    for entry in raw_grocery:
        if entry.get("done"):
            continue
        text = str(entry.get("text", "") or "").strip()
        if text:
            items.append({"name": text, "urgent": bool(entry.get("urgent", False))})
    return items


def build_dashboard_payload(
    cfg: dict[str, Any],
    sm: StateManager,
    now: datetime,
) -> dict[str, Any]:
    """Run all fetchers safely and assemble the payload for ``render_dashboard``."""
    # 1. One-shot Telegram grocery poll
    tg_token = str(
        (cfg.get("telegram", {}) if isinstance(cfg.get("telegram"), dict) else {}).get(
            "bot_token", ""
        )
        or ""
    ).strip()
    if tg_token and tg_token != "YOUR_TELEGRAM_BOT_TOKEN":
        try:
            bot = GroceryTelegramBot(config=cfg, state_manager=sm)
            processed = bot.poll_once(timeout=0)
            if processed:
                logger.info("Processed %d Telegram grocery update(s).", processed)
        except Exception as exc:
            logger.warning("Telegram one-shot poll failed: %s", exc)
    else:
        logger.debug("Telegram bot_token not configured; skipping poll.")

    # 2. Fetch Calendar (.ics)
    try:
        calendar_grouped = fetch_calendar_events(config=cfg, state_manager=sm, days=7)
    except Exception as exc:
        logger.warning("Calendar fetch failed: %s", exc)
        calendar_grouped = {}

    # 3. Fetch ilPost.it RSS
    try:
        news_items = fetch_ilpost_news(config=cfg, state_manager=sm)
    except Exception as exc:
        logger.warning("News fetch failed: %s", exc)
        news_items = []

    # 4. Fetch Open-Meteo Weather
    try:
        weather_raw = fetch_weather(config=cfg, state_manager=sm)
    except Exception as exc:
        logger.warning("Weather fetch failed: %s", exc)
        weather_raw = {}

    # 5. Fetch Commute Time
    try:
        commute_raw = fetch_commute(config=cfg, state_manager=sm)
    except Exception as exc:
        logger.warning("Commute fetch failed: %s", exc)
        commute_raw = {}

    # 6. Read updated state & resolve school menu (state -> milanoristorazione.it -> config)
    state = sm.load()
    try:
        mensa_payload = resolve_school_menu(
            state.get("school_meals", {}),
            cfg,
            now,
            state_manager=sm,
        )
    except Exception as exc:
        logger.warning("School menu resolution failed: %s", exc)
        mensa_payload = {"today": "", "tomorrow": ""}

    return {
        "last_sync": now.strftime("%H:%M"),
        "calendar_days": _adapt_calendar_days(calendar_grouped, now),
        "fixed_activities": _adapt_fixed_activities(state.get("fixed_activities")),
        "mensa": mensa_payload,
        "weather": _adapt_weather(weather_raw),
        "commute": _adapt_commute(commute_raw),
        "news": [str(item.get("title", "")) for item in news_items if item.get("title")],
        "grocery": _adapt_grocery(state.get("grocery_list", [])),
    }


def run_sync_once(
    config_path: Optional[Path] = None,
    state_path: Optional[Path] = None,
    preview_path: Path = Path("data/preview.png"),
    force_mock: Optional[bool] = None,
    no_display: bool = False,
) -> Path:
    """Execute one full sync, render, and e-Paper display update cycle."""
    cfg = load_config(config_path)
    sm = StateManager(state_path)
    tz = _resolve_timezone(cfg)
    now = datetime.now(tz)

    logger.info("Starting Smart E-Paper Calendar sync cycle (%s)...", now.isoformat())
    payload = build_dashboard_payload(cfg, sm, now)

    preview_path.parent.mkdir(parents=True, exist_ok=True)
    black_img, red_img = render_dashboard(
        payload,
        preview_path=str(preview_path),
        now=now,
    )
    logger.info("Rendered dashboard preview to %s", preview_path)

    if not no_display:
        with Waveshare7in5B(
            width=EPD_WIDTH,
            height=EPD_HEIGHT,
            mock=force_mock,
            preview_path=preview_path,
        ) as epd:
            epd.display(black_img, red_img, preview_path=preview_path)
    else:
        logger.info("--no-display set; skipping EPD hardware/mock push.")

    logger.info("Sync cycle completed successfully.")
    return preview_path


def _load_web_app():
    """Locate the FastAPI ASGI app from the project's web UI module."""
    candidates = (
        "src.web.app:app",
        "src.web_ui:app",
        "src.web.server:app",
        "app.web:app",
    )
    for target in candidates:
        module_name, attr_name = target.split(":", 1)
        try:
            mod = importlib.import_module(module_name)
            app = getattr(mod, attr_name, None)
            if app is not None:
                logger.info("Loaded LAN Web UI app from %s", target)
                return app
        except ImportError:
            continue
    return None


def run_web_server(
    config_path: Optional[Path] = None,
    sync_on_start: bool = False,
    state_path: Optional[Path] = None,
    preview_path: Path = Path("data/preview.png"),
    force_mock: Optional[bool] = None,
) -> None:
    """Start the LAN FastAPI Web UI via uvicorn."""
    import uvicorn

    cfg = load_config(config_path)
    if sync_on_start:
        try:
            run_sync_once(
                config_path=config_path,
                state_path=state_path,
                preview_path=preview_path,
                force_mock=force_mock,
            )
        except Exception as exc:
            logger.warning("Initial sync before starting Web UI failed: %s", exc)

    app = _load_web_app()
    if app is None:
        logger.error(
            "Web UI module not found (expected src.web.app:app or src.web_ui:app)."
        )
        sys.exit(1)

    web_cfg = cfg.get("web_ui", {}) if isinstance(cfg.get("web_ui"), dict) else {}
    host = str(web_cfg.get("host") or "0.0.0.0")
    port = int(web_cfg.get("port") or 8080)

    logger.info("Starting LAN Web UI on http://%s:%d ...", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")


def _install_signal_handlers() -> None:
    def _handle_signal(signum: int, _frame: Any) -> None:
        logger.info("Received signal %d; exiting cleanly.", signum)
        sys.exit(0)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smart E-Paper Calendar Orchestrator",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--sync-once",
        action="store_true",
        help="Run a single sync + render + display cycle and exit (for Witty Pi / cron).",
    )
    mode_group.add_argument(
        "--web",
        action="store_true",
        help="Run the LAN Web UI server continuously.",
    )
    parser.add_argument(
        "--sync-on-start",
        action="store_true",
        help="When using --web, perform one display sync before starting the web server.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to config.yaml (falls back to config.example.yaml if missing).",
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=DEFAULT_STATE_PATH,
        help="Path to state.json.",
    )
    parser.add_argument(
        "--preview",
        type=Path,
        default=Path("data/preview.png"),
        help="Path to save the rendered 3-color preview PNG.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Force Mock/Simulation display mode even if Raspberry Pi SPI is present.",
    )
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="Render preview PNG only without pushing to the display driver.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Logging verbosity.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    _install_signal_handlers()

    force_mock = True if args.mock else None

    if args.web:
        run_web_server(
            config_path=args.config,
            sync_on_start=args.sync_on_start,
            state_path=args.state,
            preview_path=args.preview,
            force_mock=force_mock,
        )
        return 0

    # Default (and --sync-once) executes one clean sync-render-display cycle
    run_sync_once(
        config_path=args.config,
        state_path=args.state,
        preview_path=args.preview,
        force_mock=force_mock,
        no_display=args.no_display,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
