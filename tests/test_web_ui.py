"""Integration tests for the FastAPI LAN Web UI (src/web_ui.py)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from src.config import StateManager, load_config


def _login(client: TestClient, password: str = "test-password"):
    return client.post("/login", data={"password": password}, follow_redirects=False)


def test_unauthenticated_redirects_and_401(web_client: TestClient) -> None:
    resp = web_client.get("/", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"

    prev = web_client.get("/preview.png", follow_redirects=False)
    assert prev.status_code == 401


def test_login_logout_flow(web_client: TestClient) -> None:
    login_page = web_client.get("/login")
    assert login_page.status_code == 200
    assert "Sign In" in login_page.text

    bad = _login(web_client, password="wrong-password")
    assert bad.status_code == 401
    assert "Invalid password" in bad.text

    ok = _login(web_client, password="test-password")
    assert ok.status_code == 303
    assert ok.headers["location"] == "/"
    assert "epaper_session" in web_client.cookies

    dash = web_client.get("/")
    assert dash.status_code == 200
    assert "LAN Remote Control Panel" in dash.text

    out = web_client.post("/logout", follow_redirects=False)
    assert out.status_code == 303
    assert out.headers["location"] == "/login"


def test_grocery_endpoints(web_client: TestClient, state_manager: StateManager) -> None:
    _login(web_client)

    add_resp = web_client.post("/grocery/add", data={"text": "Caffè"}, follow_redirects=False)
    assert add_resp.status_code == 303
    items = state_manager.get_grocery_list()
    assert len(items) == 1
    assert items[0]["text"] == "Caffè"
    item_id = items[0]["id"]

    tog_resp = web_client.post("/grocery/toggle", data={"id": item_id}, follow_redirects=False)
    assert tog_resp.status_code == 303
    assert state_manager.get_grocery_list()[0]["done"] is True

    del_resp = web_client.post("/grocery/delete", data={"id": item_id}, follow_redirects=False)
    assert del_resp.status_code == 303
    assert state_manager.get_grocery_list() == []


def test_meals_activities_and_settings_endpoints(
    web_client: TestClient,
    state_manager: StateManager,
    tmp_config_path: Path,
) -> None:
    _login(web_client)

    meals_resp = web_client.post(
        "/meals",
        data={"today": "Pasta al pesto", "tomorrow": "Pizza margherita"},
        follow_redirects=False,
    )
    assert meals_resp.status_code == 303
    meals = state_manager.get_school_meals()
    assert meals["today"] == "Pasta al pesto"
    assert meals["tomorrow"] == "Pizza margherita"

    act_resp = web_client.post(
        "/activities",
        data={"day_Monday": "17:00 Nuoto\n19:00 Yoga", "day_Friday": "20:00 Cinema"},
        follow_redirects=False,
    )
    assert act_resp.status_code == 303
    acts = state_manager.get_fixed_activities()
    assert acts["Monday"] == ["17:00 Nuoto", "19:00 Yoga"]
    assert acts["Friday"] == ["20:00 Cinema"]

    set_resp = web_client.post(
        "/settings",
        data={
            "home_address": "Via Torino 10, Milano",
            "office_address": "Via Dante 5, Milano",
            "ical_urls": "Work|https://example.com/work.ics\nhttps://example.com/personal.ics",
        },
        follow_redirects=False,
    )
    assert set_resp.status_code == 303
    cfg = load_config(config_path=tmp_config_path)
    assert cfg["commute"]["home_address"] == "Via Torino 10, Milano"
    assert cfg["commute"]["office_address"] == "Via Dante 5, Milano"
    assert len(cfg["calendars"]) == 2
    assert cfg["calendars"][0] == {"name": "Work", "url": "https://example.com/work.ics"}
    assert cfg["calendars"][1] == {"name": "Calendar 2", "url": "https://example.com/personal.ics"}


def test_preview_image_and_refresh(
    web_client: TestClient,
    tmp_config_path: Path,
) -> None:
    _login(web_client)

    # Missing preview -> SVG placeholder
    svg_resp = web_client.get("/preview.png")
    assert svg_resp.status_code == 200
    assert svg_resp.headers["content-type"].startswith("image/svg+xml")

    # Create PNG at configured preview_image_path -> serves PNG
    cfg = load_config(config_path=tmp_config_path)
    preview_path = Path(cfg["web_ui"]["preview_image_path"])
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (800, 480), (255, 255, 255)).save(preview_path, format="PNG")

    png_resp = web_client.get("/preview.png")
    assert png_resp.status_code == 200
    assert png_resp.headers["content-type"] == "image/png"

    # Refresh without refresh_command configured
    ref_resp = web_client.post("/refresh", follow_redirects=False)
    assert ref_resp.status_code == 303
    assert "No+refresh_command" in ref_resp.headers["location"]
