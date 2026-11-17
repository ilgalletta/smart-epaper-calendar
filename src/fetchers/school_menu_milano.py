"""Milano Ristorazione school lunch menu fetcher for Scuola Elementare Gattamelata.

Fetches the daily/weekly school lunch menu from milanoristorazione.it (HTML or
optional JSON API endpoint), caches parsed results in StateManager (data/state.json),
and falls back gracefully to cached data, state.json manual overrides, or
config.yaml ``school_menu`` when offline.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from src.config import StateManager, load_config

logger = logging.getLogger(__name__)

DEFAULT_MENU_URL = "https://www.milanoristorazione.it/il-menu-del-giorno"
DEFAULT_SCHOOL_NAME = 'Scuola Primaria "Pietro Micca" - I.C. Statale Gattamelata'
DEFAULT_SCHOOL_QUERY = "Gattamelata"
DEFAULT_AREA = "C.C. Colleoni - Area 1"
DEFAULT_CACHE_TTL_SECONDS = 6 * 60 * 60  # 6 hours
CACHE_KEY = "school_menu_milano"

ITALIAN_WEEKDAYS: dict[int, str] = {
    0: "lunedì",
    1: "martedì",
    2: "mercoledì",
    3: "giovedì",
    4: "venerdì",
    5: "sabato",
    6: "domenica",
}

ITALIAN_WEEKDAY_ALIASES: dict[str, int] = {
    "lunedi": 0,
    "lunedì": 0,
    "lun": 0,
    "monday": 0,
    "martedi": 1,
    "martedì": 1,
    "mar": 1,
    "tuesday": 1,
    "mercoledi": 2,
    "mercoledì": 2,
    "mer": 2,
    "wednesday": 2,
    "giovedi": 3,
    "giovedì": 3,
    "gio": 3,
    "thursday": 3,
    "venerdi": 4,
    "venerdì": 4,
    "ven": 4,
    "friday": 4,
    "sabato": 5,
    "sab": 5,
    "saturday": 5,
    "domenica": 6,
    "dom": 6,
    "sunday": 6,
}

_COURSE_LABELS: dict[str, tuple[str, ...]] = {
    "primo": ("primo", "primo piatto", "primi"),
    "secondo": ("secondo", "secondo piatto", "secondi", "piatto unico"),
    "contorno": ("contorno", "contorni", "verdura", "verdure"),
    "frutta": ("frutta", "frutta e pane", "pane e frutta", "dessert", "note"),
}


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def _detect_weekday(text: str) -> int | None:
    lowered = _clean_text(text).lower()
    if not lowered:
        return None
    for alias, idx in ITALIAN_WEEKDAY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", lowered):
            return idx
    return None


def _normalize_courses(raw: dict[str, Any]) -> dict[str, str]:
    primo = _clean_text(raw.get("primo", ""))
    secondo = _clean_text(raw.get("secondo", ""))
    contorno = _clean_text(raw.get("contorno", ""))
    frutta = _clean_text(raw.get("frutta") or raw.get("frutta_note") or "")
    return {
        "primo": primo,
        "secondo": secondo,
        "contorno": contorno,
        "frutta": frutta,
    }


def _has_any_course(courses: dict[str, str] | None) -> bool:
    if not isinstance(courses, dict):
        return False
    return any(
        _clean_text(courses.get(k, "")) not in ("", "—", "-")
        for k in ("primo", "secondo", "contorno", "frutta")
    )


def format_courses_line(courses: dict[str, str] | str) -> str:
    """Format a course dict into a compact comma-separated string."""
    if isinstance(courses, str):
        return _clean_text(courses)
    if not isinstance(courses, dict):
        return ""
    parts = [
        _clean_text(courses.get("primo", "")),
        _clean_text(courses.get("secondo", "")),
        _clean_text(courses.get("contorno", "")),
        _clean_text(courses.get("frutta", "")),
    ]
    return ", ".join(p for p in parts if p and p not in ("—", "-"))


def _extract_courses_from_lines(lines: list[str]) -> dict[str, str]:
    """Extract primo/secondo/contorno/frutta from labeled or ordered text lines."""
    courses = {"primo": "", "secondo": "", "contorno": "", "frutta": ""}
    unlabeled: list[str] = []

    for raw_line in lines:
        line = _clean_text(raw_line)
        if not line:
            continue
        matched = False
        for key, labels in _COURSE_LABELS.items():
            for label in labels:
                m = re.match(
                    rf"^(?:{re.escape(label)})\s*[:\-–]\s*(.+)$",
                    line,
                    flags=re.IGNORECASE,
                )
                if m:
                    val = _clean_text(m.group(1))
                    if val and not courses[key]:
                        courses[key] = val
                    matched = True
                    break
            if matched:
                break
        if not matched:
            unlabeled.append(line)

    if not _has_any_course(courses) and unlabeled:
        # Positional fallback: Primo, Secondo, Contorno, Frutta
        for idx, key in enumerate(("primo", "secondo", "contorno", "frutta")):
            if idx < len(unlabeled):
                courses[key] = unlabeled[idx]

    return courses


def parse_milanoristorazione_html(
    html_text: str,
    school_query: str = DEFAULT_SCHOOL_QUERY,
) -> dict[str, dict[str, str]]:
    """Parse milanoristorazione.it HTML into a weekday-keyed menu mapping.

    Returns a dict keyed by weekday index string (``"0"``..``"4"``) or ISO date
    where each value is ``{"primo": ..., "secondo": ..., "contorno": ..., "frutta": ...}``.
    """
    if not html_text or not html_text.strip():
        return {}

    soup = BeautifulSoup(html_text, "html.parser")
    weekly: dict[str, dict[str, str]] = {}

    # Narrow scope to a matching school container if multiple schools are listed
    root: Any = soup
    query_lower = _clean_text(school_query).lower()
    if query_lower:
        for candidate in soup.find_all(["section", "article", "div", "table"]):
            text = candidate.get_text(" ", strip=True).lower()
            if query_lower in text and len(text) < 8000:
                # Prefer the smallest container that still contains weekday or course markers
                if any(w in text for w in ("luned", "marted", "primo", "secondo")):
                    root = candidate

    # Strategy 1: HTML tables (rows or columns per weekday)
    for table in root.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue

        # Check if first row is weekday headers (column-based weekly table)
        header_cells = [
            _clean_text(c.get_text(" ", strip=True))
            for c in rows[0].find_all(["th", "td"])
        ]
        col_weekdays: dict[int, int] = {}
        for col_idx, cell_text in enumerate(header_cells):
            wd = _detect_weekday(cell_text)
            if wd is not None:
                col_weekdays[col_idx] = wd

        if len(col_weekdays) >= 2:
            col_lines: dict[int, list[str]] = {wd: [] for wd in col_weekdays.values()}
            for row in rows[1:]:
                cells = row.find_all(["th", "td"])
                row_label = (
                    _clean_text(cells[0].get_text(" ", strip=True)) if cells else ""
                )
                for col_idx, wd in col_weekdays.items():
                    if col_idx < len(cells):
                        val = _clean_text(cells[col_idx].get_text(" ", strip=True))
                        if val:
                            if col_idx > 0 and row_label and _detect_weekday(row_label) is None:
                                col_lines[wd].append(f"{row_label}: {val}")
                            else:
                                col_lines[wd].append(val)
            for wd, lines in col_lines.items():
                courses = _extract_courses_from_lines(lines)
                if _has_any_course(courses):
                    weekly[str(wd)] = courses
            if weekly:
                return weekly

        # Row-based table (each row starts with a weekday name)
        for row in rows:
            cells = [
                _clean_text(c.get_text(" ", strip=True))
                for c in row.find_all(["th", "td"])
            ]
            if not cells:
                continue
            wd = _detect_weekday(cells[0])
            if wd is not None:
                courses = _extract_courses_from_lines(cells[1:])
                if _has_any_course(courses):
                    weekly[str(wd)] = courses
        if weekly:
            return weekly

    # Strategy 2: Day cards / divs / list items
    for block in root.find_all(["div", "article", "section", "li"]):
        heading = block.find(["h1", "h2", "h3", "h4", "strong", "span", "dt"])
        heading_text = _clean_text(heading.get_text(" ", strip=True)) if heading else ""
        wd = _detect_weekday(heading_text)
        if wd is None:
            continue
        raw_lines = [
            _clean_text(el.get_text(" ", strip=True))
            for el in block.find_all(["p", "li", "dd", "div", "span"])
        ]
        # Deduplicate while preserving order
        seen: set[str] = set()
        lines: list[str] = []
        for line in raw_lines:
            if line and line != heading_text and line not in seen:
                seen.add(line)
                lines.append(line)
        courses = _extract_courses_from_lines(lines)
        if _has_any_course(courses):
            weekly[str(wd)] = courses

    # Strategy 3: Single-day page (no weekday header, just Primo/Secondo/Contorno/Frutta)
    if not weekly:
        text_lines = [
            _clean_text(line)
            for line in root.get_text("\n", strip=True).splitlines()
        ]
        courses = _extract_courses_from_lines(text_lines)
        if _has_any_course(courses):
            weekly["current"] = courses

    return weekly


def parse_milanoristorazione_json(
    payload: Any,
    school_query: str = DEFAULT_SCHOOL_QUERY,
) -> dict[str, dict[str, str]]:
    """Parse a JSON API payload into a weekday-keyed menu mapping."""
    weekly: dict[str, dict[str, str]] = {}
    if isinstance(payload, dict):
        # Direct today/tomorrow shape
        if "today" in payload or "tomorrow" in payload:
            for key in ("today", "tomorrow"):
                val = payload.get(key)
                if isinstance(val, dict):
                    courses = _normalize_courses(val)
                    if _has_any_course(courses):
                        weekly[key] = courses
            if weekly:
                return weekly

        # List container keys (e.g., MenuSettimanale ``pasti_scuola`` or ``days``)
        for list_key in ("pasti_scuola", "days", "menu", "items", "results"):
            entries = payload.get(list_key)
            if isinstance(entries, list):
                payload = entries
                break

    if isinstance(payload, list):
        query_lower = _clean_text(school_query).lower()
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            school_field = _clean_text(
                entry.get("scuola") or entry.get("school") or ""
            ).lower()
            if query_lower and school_field and query_lower not in school_field:
                continue
            day_label = _clean_text(
                entry.get("giorno") or entry.get("day") or entry.get("date") or ""
            )
            wd = _detect_weekday(day_label)
            courses = _normalize_courses(entry)
            if _has_any_course(courses):
                key = str(wd) if wd is not None else day_label
                if key:
                    weekly[key] = courses

    return weekly


def _select_day_menu(
    weekly: dict[str, dict[str, str]],
    target_date: date,
    is_today: bool = True,
) -> dict[str, str] | str:
    """Pick the menu for ``target_date`` from a parsed weekly dict."""
    if not isinstance(weekly, dict) or not weekly:
        return ""

    # Direct today/tomorrow keys
    direct_key = "today" if is_today else "tomorrow"
    if direct_key in weekly and _has_any_course(weekly[direct_key]):
        return weekly[direct_key]

    # ISO date key
    iso_key = target_date.isoformat()
    if iso_key in weekly and _has_any_course(weekly[iso_key]):
        return weekly[iso_key]

    # Weekday index key ("0".."6")
    wd_key = str(target_date.weekday())
    if wd_key in weekly and _has_any_course(weekly[wd_key]):
        return weekly[wd_key]

    # Single-day fallback only for today
    if is_today and "current" in weekly and _has_any_course(weekly["current"]):
        return weekly["current"]

    return ""


def fetch_milanoristorazione_menu(
    config: dict[str, Any] | None = None,
    state_manager: StateManager | None = None,
    now: datetime | None = None,
    timeout: int = 12,
) -> dict[str, Any]:
    """Fetch Scuola Elementare Gattamelata menu from milanoristorazione.it.

    Uses StateManager local JSON cache (``cache["school_menu_milano"]``) to avoid
    redundant requests within ``cache_ttl_seconds`` and falls back to stale cache
    if milanoristorazione.it is unreachable or offline.
    """
    cfg = config if config is not None else load_config()
    sm = state_manager if state_manager is not None else StateManager()

    mr_cfg = (
        cfg.get("milanoristorazione", {})
        if isinstance(cfg.get("milanoristorazione"), dict)
        else {}
    )
    if mr_cfg.get("enabled", True) is False:
        return {"today": "", "tomorrow": "", "source": "disabled"}

    if now is None:
        tz_name = str(cfg.get("timezone") or "Europe/Rome")
        try:
            now = datetime.now(ZoneInfo(tz_name))
        except Exception:
            now = datetime.now()

    today_date = now.date()
    tomorrow_date = today_date + timedelta(days=1)

    school_name = str(mr_cfg.get("school_name") or DEFAULT_SCHOOL_NAME)
    school_query = str(mr_cfg.get("school_query") or DEFAULT_SCHOOL_QUERY)
    menu_url = str(mr_cfg.get("menu_url") or DEFAULT_MENU_URL).strip()
    api_url = str(mr_cfg.get("api_url") or "").strip()
    ttl = int(mr_cfg.get("cache_ttl_seconds") or DEFAULT_CACHE_TTL_SECONDS)

    # 1. Fresh cache hit
    fresh_cached = sm.get_cache(CACHE_KEY, max_age_seconds=ttl)
    if isinstance(fresh_cached, dict) and isinstance(fresh_cached.get("weekly"), dict):
        weekly = fresh_cached["weekly"]
        return {
            "school": fresh_cached.get("school", school_name),
            "weekly": weekly,
            "today": _select_day_menu(weekly, today_date, is_today=True),
            "tomorrow": _select_day_menu(weekly, tomorrow_date, is_today=False),
            "source": "cache",
        }

    # 2. Live fetch (JSON API if configured, else HTML page)
    headers = {
        "User-Agent": "smart-epaper-calendar/1.0 (+https://github.com/smart-epaper-calendar)",
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.5",
    }
    weekly: dict[str, dict[str, str]] = {}
    target_url = api_url or menu_url
    try:
        resp = requests.get(target_url, timeout=timeout, headers=headers)
        resp.raise_for_status()
        content_type = str(resp.headers.get("Content-Type", "")).lower()
        if api_url or "application/json" in content_type:
            weekly = parse_milanoristorazione_json(resp.json(), school_query=school_query)
        else:
            weekly = parse_milanoristorazione_html(resp.text, school_query=school_query)

        if weekly:
            cached_payload = {
                "school": school_name,
                "area": str(mr_cfg.get("area") or DEFAULT_AREA),
                "url": target_url,
                "weekly": weekly,
            }
            sm.set_cache(CACHE_KEY, cached_payload)
            return {
                "school": school_name,
                "weekly": weekly,
                "today": _select_day_menu(weekly, today_date, is_today=True),
                "tomorrow": _select_day_menu(weekly, tomorrow_date, is_today=False),
                "source": "live",
            }
        logger.warning(
            "milanoristorazione.it returned no parseable menu for %r (%s).",
            school_query,
            target_url,
        )
    except Exception as exc:
        logger.warning(
            "Failed to fetch milanoristorazione.it menu (%s): %s", target_url, exc
        )

    # 3. Stale cache fallback when offline
    stale_cached = sm.get_cache(CACHE_KEY)
    if isinstance(stale_cached, dict) and isinstance(stale_cached.get("weekly"), dict):
        logger.info("Using stale cached milanoristorazione.it menu.")
        weekly = stale_cached["weekly"]
        return {
            "school": stale_cached.get("school", school_name),
            "weekly": weekly,
            "today": _select_day_menu(weekly, today_date, is_today=True),
            "tomorrow": _select_day_menu(weekly, tomorrow_date, is_today=False),
            "source": "stale_cache",
        }

    return {"school": school_name, "weekly": {}, "today": "", "tomorrow": "", "source": "none"}


def resolve_school_menu(
    state_meals: dict[str, Any] | None,
    cfg: dict[str, Any],
    now: datetime,
    state_manager: StateManager | None = None,
) -> dict[str, Any]:
    """Resolve ``mensa`` payload for the e-Paper dashboard.

    Resolution order:
      1. Non-empty manual override in ``state.json["school_meals"]`` (Web UI).
      2. Live or cached menu from ``milanoristorazione.it`` (Gattamelata).
      3. Static fallback in ``config.yaml["school_menu"]["week_1"]``.
    """
    meals = state_meals if isinstance(state_meals, dict) else {}
    today_val: Any = str(meals.get("today", "") or "").strip()
    tomorrow_val: Any = str(meals.get("tomorrow", "") or "").strip()

    if today_val or tomorrow_val:
        return {"today": today_val, "tomorrow": tomorrow_val}

    mr_result = fetch_milanoristorazione_menu(
        config=cfg,
        state_manager=state_manager,
        now=now,
    )
    mr_today = mr_result.get("today", "")
    mr_tomorrow = mr_result.get("tomorrow", "")
    if _has_any_course(mr_today) or _has_any_course(mr_tomorrow) or mr_today or mr_tomorrow:
        return {"today": mr_today, "tomorrow": mr_tomorrow}

    # Graceful fallback to config.yaml static rotating/weekly school_menu
    menu_cfg = cfg.get("school_menu", {})
    if isinstance(menu_cfg, dict):
        week_1 = menu_cfg.get("week_1", menu_cfg)
        if isinstance(week_1, dict):
            today_key = now.strftime("%A").lower()
            tomorrow_key = (now + timedelta(days=1)).strftime("%A").lower()
            today_val = str(week_1.get(today_key, "") or "").strip()
            tomorrow_val = str(week_1.get(tomorrow_key, "") or "").strip()

    return {"today": today_val, "tomorrow": tomorrow_val}
