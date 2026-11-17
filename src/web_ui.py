"""LAN-accessible FastAPI Remote Web UI with signed-cookie authentication."""

from __future__ import annotations

import hmac
import html
import logging
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote_plus

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from src.config import (
    DAYS_OF_WEEK,
    PROJECT_ROOT,
    StateManager,
    load_config,
    save_config,
)

logger = logging.getLogger(__name__)

SESSION_COOKIE_NAME = "epaper_session"

_PLACEHOLDER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="800" height="480" viewBox="0 0 800 480">
  <rect width="800" height="480" fill="#f8fafc" stroke="#cbd5e1" stroke-width="4"/>
  <text x="400" y="225" text-anchor="middle" font-family="sans-serif" font-size="24" fill="#475569">
    No rendered e-paper image found yet
  </text>
  <text x="400" y="260" text-anchor="middle" font-family="sans-serif" font-size="15" fill="#94a3b8">
    Click "Refresh Display Now" or run the display renderer to generate 800x480 preview
  </text>
</svg>"""


async def _parse_form(request: Request) -> dict[str, list[str]]:
    body = (await request.body()).decode("utf-8", errors="replace")
    return parse_qs(body, keep_blank_values=True)


def _form_first(form: dict[str, list[str]], key: str, default: str = "") -> str:
    vals = form.get(key)
    if not vals:
        return default
    return vals[0]


def _get_serializer(cfg: dict[str, Any]) -> URLSafeTimedSerializer:
    secret = str(cfg.get("web_ui", {}).get("session_secret") or "dev-secret-change-me")
    return URLSafeTimedSerializer(secret, salt="epaper-web-ui-session")


def _is_authenticated(request: Request, cfg: dict[str, Any]) -> bool:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return False
    max_age = int(cfg.get("web_ui", {}).get("session_max_age_seconds") or 604800)
    serializer = _get_serializer(cfg)
    try:
        data = serializer.loads(token, max_age=max_age)
        return isinstance(data, dict) and data.get("auth") is True
    except (BadSignature, SignatureExpired):
        return False


def _require_auth_redirect(request: Request, cfg: dict[str, Any]) -> RedirectResponse | None:
    if not _is_authenticated(request, cfg):
        return RedirectResponse(url="/login", status_code=303)
    return None


def _render_login_page(error: str = "") -> str:
    err_html = (
        f'<div class="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{html.escape(error)}</div>'
        if error
        else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Smart E-Paper Calendar - Login</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="min-h-screen bg-slate-100 flex items-center justify-center p-4">
  <div class="w-full max-w-sm bg-white rounded-2xl shadow-md border border-slate-200 p-6">
    <h1 class="text-xl font-semibold text-slate-800 mb-1">Smart E-Paper Calendar</h1>
    <p class="text-sm text-slate-500 mb-5">Sign in to manage your display on the LAN</p>
    {err_html}
    <form method="post" action="/login" class="space-y-4">
      <div>
        <label for="password" class="block text-sm font-medium text-slate-700 mb-1">Password</label>
        <input id="password" name="password" type="password" required autofocus
          class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-800"/>
      </div>
      <button type="submit"
        class="w-full rounded-lg bg-slate-900 text-white py-2 text-sm font-medium hover:bg-slate-800 transition">
        Sign In
      </button>
    </form>
  </div>
</body>
</html>"""


def _render_dashboard(
    cfg: dict[str, Any],
    sm: StateManager,
    notice: str = "",
) -> str:
    groceries = sm.get_grocery_list()
    activities = sm.get_fixed_activities()
    meals = sm.get_school_meals()

    commute_cfg = cfg.get("commute", {}) if isinstance(cfg.get("commute"), dict) else {}
    home_addr = html.escape(str(commute_cfg.get("home_address", "") or ""))
    office_addr = html.escape(str(commute_cfg.get("office_address", "") or ""))

    raw_cals = cfg.get("calendars", [])
    ical_lines: list[str] = []
    if isinstance(raw_cals, list):
        for item in raw_cals:
            if isinstance(item, str) and item.strip():
                ical_lines.append(item.strip())
            elif isinstance(item, dict) and str(item.get("url", "")).strip():
                name = str(item.get("name", "")).strip()
                url = str(item["url"]).strip()
                ical_lines.append(f"{name}|{url}" if name else url)
    ical_text = html.escape("\n".join(ical_lines))

    notice_html = (
        f'<div class="mb-6 rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-800">{html.escape(notice)}</div>'
        if notice
        else ""
    )

    grocery_rows = []
    for item in groceries:
        iid = html.escape(str(item.get("id", "")))
        text = html.escape(str(item.get("text", "")))
        done = bool(item.get("done", False))
        strike = "line-through text-slate-400" if done else "text-slate-800"
        btn_label = "Undo" if done else "Done"
        grocery_rows.append(
            f"""<li class="flex items-center justify-between gap-2 py-2 border-b border-slate-100 last:border-0">
              <span class="text-sm {strike} flex-1">{text}</span>
              <div class="flex items-center gap-1.5">
                <form method="post" action="/grocery/toggle">
                  <input type="hidden" name="id" value="{iid}"/>
                  <button type="submit" class="px-2.5 py-1 text-xs rounded-md border border-slate-300 hover:bg-slate-100">{btn_label}</button>
                </form>
                <form method="post" action="/grocery/delete">
                  <input type="hidden" name="id" value="{iid}"/>
                  <button type="submit" class="px-2.5 py-1 text-xs rounded-md border border-red-200 text-red-600 hover:bg-red-50">Delete</button>
                </form>
              </div>
            </li>"""
        )
    grocery_list_html = (
        "".join(grocery_rows)
        if grocery_rows
        else '<li class="py-3 text-sm text-slate-400">No items yet.</li>'
    )

    activity_inputs = []
    for day in DAYS_OF_WEEK:
        day_items = "\n".join(activities.get(day, []))
        activity_inputs.append(
            f"""<div>
              <label class="block text-xs font-medium text-slate-600 mb-1">{day}</label>
              <textarea name="day_{day}" rows="2" placeholder="One activity per line"
                class="w-full rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-slate-800">{html.escape(day_items)}</textarea>
            </div>"""
        )

    today_meal = html.escape(str(meals.get("today", "") or ""))
    tomorrow_meal = html.escape(str(meals.get("tomorrow", "") or ""))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Smart E-Paper Calendar - Control Panel</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="min-h-screen bg-slate-100 text-slate-900">
  <header class="bg-white border-b border-slate-200 sticky top-0 z-10">
    <div class="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
      <div>
        <h1 class="text-lg font-semibold text-slate-800">Smart E-Paper Calendar</h1>
        <p class="text-xs text-slate-500">LAN Remote Control Panel</p>
      </div>
      <div class="flex items-center gap-2">
        <form method="post" action="/refresh">
          <button type="submit"
            class="rounded-lg bg-slate-900 text-white px-3.5 py-1.5 text-xs font-medium hover:bg-slate-800 transition">
            Refresh Display Now
          </button>
        </form>
        <form method="post" action="/logout">
          <button type="submit"
            class="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100 transition">
            Logout
          </button>
        </form>
      </div>
    </div>
  </header>

  <main class="max-w-5xl mx-auto px-4 py-6 space-y-6">
    {notice_html}

    <!-- Preview -->
    <section class="bg-white rounded-2xl shadow-sm border border-slate-200 p-5">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-base font-semibold text-slate-800">Latest E-Paper Preview (800×480)</h2>
        <a href="/preview.png" target="_blank" class="text-xs text-slate-500 hover:text-slate-800 underline">Open full size</a>
      </div>
      <div class="rounded-xl overflow-hidden border border-slate-200 bg-slate-50 flex justify-center">
        <img src="/preview.png" alt="800x480 E-Paper Preview" class="max-w-full h-auto"/>
      </div>
    </section>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <!-- Grocery List -->
      <section class="bg-white rounded-2xl shadow-sm border border-slate-200 p-5">
        <h2 class="text-base font-semibold text-slate-800 mb-3">Grocery List</h2>
        <form method="post" action="/grocery/add" class="flex gap-2 mb-4">
          <input name="text" type="text" required placeholder="Add item (e.g. Milk, Apples)..."
            class="flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-slate-800"/>
          <button type="submit" class="rounded-lg bg-slate-900 text-white px-3.5 py-1.5 text-sm font-medium hover:bg-slate-800">Add</button>
        </form>
        <ul class="divide-y divide-slate-100">
          {grocery_list_html}
        </ul>
      </section>

      <!-- School Meals -->
      <section class="bg-white rounded-2xl shadow-sm border border-slate-200 p-5">
        <h2 class="text-base font-semibold text-slate-800 mb-3">School Meals</h2>
        <form method="post" action="/meals" class="space-y-3">
          <div>
            <label class="block text-xs font-medium text-slate-600 mb-1">Today's Meal</label>
            <textarea name="today" rows="3" placeholder="e.g. Pasta al pomodoro, chicken, fruit"
              class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-800">{today_meal}</textarea>
          </div>
          <div>
            <label class="block text-xs font-medium text-slate-600 mb-1">Tomorrow's Meal</label>
            <textarea name="tomorrow" rows="3" placeholder="e.g. Risotto, fish, salad"
              class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-800">{tomorrow_meal}</textarea>
          </div>
          <button type="submit" class="rounded-lg bg-slate-900 text-white px-4 py-1.5 text-sm font-medium hover:bg-slate-800">
            Save School Meals
          </button>
        </form>
      </section>
    </div>

    <!-- Fixed Weekly Activities -->
    <section class="bg-white rounded-2xl shadow-sm border border-slate-200 p-5">
      <h2 class="text-base font-semibold text-slate-800 mb-3">Fixed Weekly Activities</h2>
      <form method="post" action="/activities" class="space-y-4">
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {"".join(activity_inputs)}
        </div>
        <button type="submit" class="rounded-lg bg-slate-900 text-white px-4 py-1.5 text-sm font-medium hover:bg-slate-800">
          Save Weekly Activities
        </button>
      </form>
    </section>

    <!-- Settings: Addresses & iCal URLs -->
    <section class="bg-white rounded-2xl shadow-sm border border-slate-200 p-5">
      <h2 class="text-base font-semibold text-slate-800 mb-3">Commute Addresses &amp; iCal URLs</h2>
      <form method="post" action="/settings" class="space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-xs font-medium text-slate-600 mb-1">Home Address</label>
            <input name="home_address" type="text" value="{home_addr}" placeholder="Via Roma 1, Milano"
              class="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-slate-800"/>
          </div>
          <div>
            <label class="block text-xs font-medium text-slate-600 mb-1">Office Address</label>
            <input name="office_address" type="text" value="{office_addr}" placeholder="Piazza Duomo, Milano"
              class="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-slate-800"/>
          </div>
        </div>
        <div>
          <label class="block text-xs font-medium text-slate-600 mb-1">
            Google Calendar iCal URLs (one per line, optionally <code>Name|https://...</code>)
          </label>
          <textarea name="ical_urls" rows="3" placeholder="Family|https://calendar.google.com/calendar/ical/.../basic.ics"
            class="w-full rounded-lg border border-slate-300 px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-slate-800">{ical_text}</textarea>
        </div>
        <button type="submit" class="rounded-lg bg-slate-900 text-white px-4 py-1.5 text-sm font-medium hover:bg-slate-800">
          Save Settings
        </button>
      </form>
    </section>
  </main>
</body>
</html>"""


def create_app(
    config_path: str | Path | None = None,
    state_manager: StateManager | None = None,
) -> FastAPI:
    """Create and configure the FastAPI LAN Remote Web UI application."""
    app = FastAPI(title="Smart E-Paper Calendar Web UI")
    sm = state_manager if state_manager is not None else StateManager()

    def _cfg() -> dict[str, Any]:
        return load_config(config_path=config_path)

    @app.get("/login", response_class=HTMLResponse)
    async def login_get(request: Request) -> Response:
        cfg = _cfg()
        if _is_authenticated(request, cfg):
            return RedirectResponse(url="/", status_code=303)
        return HTMLResponse(_render_login_page())

    @app.post("/login")
    async def login_post(request: Request) -> Response:
        cfg = _cfg()
        form = await _parse_form(request)
        submitted = _form_first(form, "password")
        expected = str(cfg.get("web_ui", {}).get("password") or "changeme")

        if not hmac.compare_digest(submitted, expected):
            return HTMLResponse(_render_login_page("Invalid password."), status_code=401)

        serializer = _get_serializer(cfg)
        token = serializer.dumps({"auth": True})
        max_age = int(cfg.get("web_ui", {}).get("session_max_age_seconds") or 604800)

        resp = RedirectResponse(url="/", status_code=303)
        resp.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=token,
            max_age=max_age,
            httponly=True,
            samesite="lax",
        )
        return resp

    @app.post("/logout")
    @app.get("/logout")
    async def logout() -> RedirectResponse:
        resp = RedirectResponse(url="/login", status_code=303)
        resp.delete_cookie(SESSION_COOKIE_NAME)
        return resp

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request, notice: str = "") -> Response:
        cfg = _cfg()
        redir = _require_auth_redirect(request, cfg)
        if redir is not None:
            return redir
        return HTMLResponse(_render_dashboard(cfg, sm, notice=notice))

    @app.post("/grocery/add")
    async def grocery_add(request: Request) -> RedirectResponse:
        cfg = _cfg()
        redir = _require_auth_redirect(request, cfg)
        if redir is not None:
            return redir
        form = await _parse_form(request)
        text = _form_first(form, "text").strip()
        if text:
            sm.add_grocery_item(text)
            return RedirectResponse(url="/?notice=" + quote_plus("Grocery item added."), status_code=303)
        return RedirectResponse(url="/", status_code=303)

    @app.post("/grocery/toggle")
    async def grocery_toggle(request: Request) -> RedirectResponse:
        cfg = _cfg()
        redir = _require_auth_redirect(request, cfg)
        if redir is not None:
            return redir
        form = await _parse_form(request)
        item_id = _form_first(form, "id").strip()
        if item_id:
            sm.toggle_grocery_item(item_id)
        return RedirectResponse(url="/", status_code=303)

    @app.post("/grocery/delete")
    async def grocery_delete(request: Request) -> RedirectResponse:
        cfg = _cfg()
        redir = _require_auth_redirect(request, cfg)
        if redir is not None:
            return redir
        form = await _parse_form(request)
        item_id = _form_first(form, "id").strip()
        if item_id:
            sm.delete_grocery_item(item_id)
        return RedirectResponse(url="/", status_code=303)

    @app.post("/activities")
    async def update_activities(request: Request) -> RedirectResponse:
        cfg = _cfg()
        redir = _require_auth_redirect(request, cfg)
        if redir is not None:
            return redir
        form = await _parse_form(request)
        updated: dict[str, list[str]] = {}
        for day in DAYS_OF_WEEK:
            raw = _form_first(form, f"day_{day}")
            updated[day] = [line.strip() for line in raw.splitlines() if line.strip()]
        sm.set_fixed_activities(updated)
        return RedirectResponse(
            url="/?notice=" + quote_plus("Weekly activities saved."),
            status_code=303,
        )

    @app.post("/meals")
    async def update_meals(request: Request) -> RedirectResponse:
        cfg = _cfg()
        redir = _require_auth_redirect(request, cfg)
        if redir is not None:
            return redir
        form = await _parse_form(request)
        today_meal = _form_first(form, "today")
        tomorrow_meal = _form_first(form, "tomorrow")
        sm.set_school_meals(today_meal, tomorrow_meal)
        return RedirectResponse(
            url="/?notice=" + quote_plus("School meals saved."),
            status_code=303,
        )

    @app.post("/settings")
    async def update_settings(request: Request) -> RedirectResponse:
        cfg = _cfg()
        redir = _require_auth_redirect(request, cfg)
        if redir is not None:
            return redir
        form = await _parse_form(request)
        home_addr = _form_first(form, "home_address").strip()
        office_addr = _form_first(form, "office_address").strip()
        raw_icals = _form_first(form, "ical_urls")

        calendars: list[dict[str, str]] = []
        for idx, line in enumerate(raw_icals.splitlines(), start=1):
            cleaned = line.strip()
            if not cleaned:
                continue
            if "|" in cleaned:
                name, url = cleaned.split("|", 1)
                calendars.append({"name": name.strip() or f"Calendar {idx}", "url": url.strip()})
            else:
                calendars.append({"name": f"Calendar {idx}", "url": cleaned})

        cfg.setdefault("commute", {})
        cfg["commute"]["home_address"] = home_addr
        cfg["commute"]["office_address"] = office_addr
        # Clear cached coords when addresses change so next commute fetch re-geocodes
        cfg["commute"]["home_coords"] = None
        cfg["commute"]["office_coords"] = None
        cfg["calendars"] = calendars

        save_config(cfg, config_path=config_path)
        return RedirectResponse(
            url="/?notice=" + quote_plus("Settings saved to config.yaml."),
            status_code=303,
        )

    @app.get("/preview.png")
    async def preview_image(request: Request) -> Response:
        cfg = _cfg()
        if not _is_authenticated(request, cfg):
            raise HTTPException(status_code=401, detail="Authentication required")

        raw_path = str(
            cfg.get("web_ui", {}).get("preview_image_path") or "data/latest_render.png"
        )
        img_path = Path(raw_path)
        if not img_path.is_absolute():
            img_path = PROJECT_ROOT / img_path

        if img_path.exists() and img_path.is_file():
            return FileResponse(str(img_path), media_type="image/png")
        return Response(content=_PLACEHOLDER_SVG, media_type="image/svg+xml")

    @app.post("/refresh")
    async def refresh_display(request: Request) -> RedirectResponse:
        cfg = _cfg()
        redir = _require_auth_redirect(request, cfg)
        if redir is not None:
            return redir

        cmd_str = str(cfg.get("web_ui", {}).get("refresh_command") or "").strip()
        if not cmd_str:
            return RedirectResponse(
                url="/?notice="
                + quote_plus("No refresh_command configured in config.yaml; state is saved."),
                status_code=303,
            )

        try:
            args = shlex.split(cmd_str)
            subprocess.Popen(args, cwd=str(PROJECT_ROOT))
            msg = "Display refresh triggered."
        except Exception as exc:
            logger.error("Failed to launch refresh_command %r: %s", cmd_str, exc)
            msg = f"Failed to trigger refresh: {exc}"

        return RedirectResponse(url="/?notice=" + quote_plus(msg), status_code=303)

    return app


app = create_app()


def run_server() -> None:
    cfg = load_config()
    web_cfg = cfg.get("web_ui", {}) if isinstance(cfg.get("web_ui"), dict) else {}
    host = str(web_cfg.get("host") or "0.0.0.0")
    port = int(os.environ.get("EPAPER_WEB_PORT", web_cfg.get("port") or 8080))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_server()
