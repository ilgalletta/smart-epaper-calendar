"""Integration tests for src/main.py orchestrator and src/telegram_bot.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from src.config import StateManager
from src.main import run_sync_once
from src.telegram_bot import GroceryTelegramBot


def test_run_sync_once_end_to_end_mock(
    tmp_path: Path,
    tmp_config_path: Path,
    tmp_state_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sm = StateManager(state_path=tmp_state_path)
    sm.add_grocery_item("Latte")
    sm.set_fixed_activities({"Monday": ["18:00 Nuoto"]})
    sm.set_school_meals("Pasta al pomodoro", "Risotto")

    monkeypatch.setattr(
        "src.main.fetch_calendar_events",
        lambda **kw: {},
    )
    monkeypatch.setattr(
        "src.main.fetch_ilpost_news",
        lambda **kw: [{"title": "Notizia di test"}],
    )
    monkeypatch.setattr(
        "src.main.fetch_weather",
        lambda **kw: {
            "location": "Milano",
            "current": {"temperature": 18, "description": "Sereno", "icon": "sun"},
            "today": {"temp_min": 11, "temp_max": 22},
        },
    )
    monkeypatch.setattr(
        "src.main.fetch_commute",
        lambda **kw: {
            "provider": "osrm",
            "duration_minutes": 20,
            "duration_text": "20 min",
            "destination": "Ufficio",
        },
    )

    out_preview = tmp_path / "out" / "preview.png"
    result_path = run_sync_once(
        config_path=tmp_config_path,
        state_path=tmp_state_path,
        preview_path=out_preview,
        force_mock=True,
    )

    assert result_path == out_preview
    assert out_preview.exists()
    with Image.open(out_preview) as im:
        assert im.size == (800, 480)
        assert im.mode == "RGB"


def test_telegram_bot_commands_and_authorization(
    state_manager: StateManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = GroceryTelegramBot(
        bot_token="123456:TESTTOKEN",
        allowed_chat_ids=[1001],
        state_manager=state_manager,
        config={},
    )

    sent_messages: list[tuple[int, str]] = []
    monkeypatch.setattr(
        bot,
        "send_message",
        lambda cid, txt: sent_messages.append((cid, txt)) or True,
    )

    # Unauthorized chat_id is ignored
    unauth = bot.process_update(
        {"update_id": 1, "message": {"chat": {"id": 9999}, "text": "/add Pane"}}
    )
    assert unauth is None
    assert state_manager.get_grocery_list() == []

    # Authorized /add, /list, /done, /clear
    r1 = bot.process_update(
        {"update_id": 2, "message": {"chat": {"id": 1001}, "text": "/add Mele"}}
    )
    assert r1 == "Added: Mele"

    r2 = bot.process_update(
        {"update_id": 3, "message": {"chat": {"id": 1001}, "text": "/list"}}
    )
    assert "1. [ ] Mele" in (r2 or "")

    r3 = bot.process_update(
        {"update_id": 4, "message": {"chat": {"id": 1001}, "text": "/done 1"}}
    )
    assert r3 == "Marked done: Mele"

    r4 = bot.process_update(
        {"update_id": 5, "message": {"chat": {"id": 1001}, "text": "/clear"}}
    )
    assert r4 == "Cleared 1 completed item(s)."
    assert len(sent_messages) == 4


def test_telegram_bot_poll_once_updates_offset(
    state_manager: StateManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = GroceryTelegramBot(
        bot_token="123456:TESTTOKEN",
        allowed_chat_ids=[1001],
        state_manager=state_manager,
        config={},
    )
    monkeypatch.setattr(bot, "send_message", lambda cid, txt: True)

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {
        "ok": True,
        "result": [
            {"update_id": 10, "message": {"chat": {"id": 1001}, "text": "/add Latte"}},
            {"update_id": 11, "message": {"chat": {"id": 1001}, "text": "not a command"}},
        ],
    }
    monkeypatch.setattr("src.telegram_bot.requests.get", lambda *a, **kw: mock_resp)

    processed = bot.poll_once(timeout=0)
    assert processed == 1
    assert state_manager.get_telegram_offset() == 11
    assert len(state_manager.get_grocery_list()) == 1
