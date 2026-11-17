"""Unit tests for src/config.py (configuration loading/saving & StateManager)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.config import (
    DAYS_OF_WEEK,
    StateManager,
    load_config,
    resolve_config_path,
    save_config,
)


def test_load_config_defaults_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EPAPER_CONFIG_PATH", raising=False)
    monkeypatch.setattr("src.config.DEFAULT_CONFIG_PATH", tmp_path / "nonexistent.yaml")
    monkeypatch.setattr("src.config.DEFAULT_EXAMPLE_CONFIG_PATH", tmp_path / "nonexistent_ex.yaml")

    cfg = load_config()
    assert cfg["timezone"] == "Europe/Rome"
    assert cfg["web_ui"]["password"] == "changeme"
    assert cfg["web_ui"]["session_secret"]  # auto-generated


def test_save_and_load_config_roundtrip(tmp_path: Path) -> None:
    cfg_path = tmp_path / "nested" / "config.yaml"
    save_config({"timezone": "UTC", "web_ui": {"port": 9090}}, config_path=cfg_path)
    assert cfg_path.exists()

    loaded = load_config(config_path=cfg_path)
    assert loaded["timezone"] == "UTC"
    assert loaded["web_ui"]["port"] == 9090
    # Default keys preserved via deep merge
    assert loaded["news"]["max_items"] == 3


def test_resolve_config_falls_back_to_example(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EPAPER_CONFIG_PATH", raising=False)
    monkeypatch.setattr("src.config.DEFAULT_CONFIG_PATH", tmp_path / "missing.yaml")
    ex = tmp_path / "config.example.yaml"
    ex.write_text("general:\n  timezone: Europe/Rome\n", encoding="utf-8")

    resolved = resolve_config_path(example_path=ex)
    assert resolved == ex


def test_load_config_handles_non_mapping_yaml(tmp_path: Path) -> None:
    bad_cfg = tmp_path / "bad.yaml"
    bad_cfg.write_text("- just\n- a\n- list\n", encoding="utf-8")
    cfg = load_config(config_path=bad_cfg)
    assert cfg["timezone"] == "Europe/Rome"


def test_state_manager_missing_and_corrupt_json(tmp_state_path: Path) -> None:
    sm = StateManager(state_path=tmp_state_path)
    state = sm.load()
    assert state["grocery_list"] == []
    assert list(state["fixed_activities"].keys()) == list(DAYS_OF_WEEK)

    tmp_state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_state_path.write_text("{corrupt json", encoding="utf-8")
    recovered = sm.load()
    assert recovered["grocery_list"] == []
    assert recovered["telegram"]["last_update_id"] == 0


def test_state_manager_grocery_crud(state_manager: StateManager) -> None:
    with pytest.raises(ValueError):
        state_manager.add_grocery_item("   ")

    item1 = state_manager.add_grocery_item("Latte fresco")
    item2 = state_manager.add_grocery_item("Pane integrale")
    assert item1["done"] is False
    assert len(state_manager.get_grocery_list()) == 2

    # Toggle by ID
    toggled = state_manager.toggle_grocery_item(item1["id"])
    assert toggled is not None and toggled["done"] is True

    # Mark done by substring
    marked = state_manager.mark_grocery_done("pane")
    assert marked is not None and marked["done"] is True

    # Clear completed only
    removed = state_manager.clear_grocery_list(completed_only=True)
    assert removed == 2
    assert state_manager.get_grocery_list() == []

    # Add & mark by 1-based index, then delete
    item3 = state_manager.add_grocery_item("Mele")
    assert state_manager.mark_grocery_done("1")["id"] == item3["id"]
    assert state_manager.delete_grocery_item(item3["id"]) is True
    assert state_manager.delete_grocery_item("missing") is False


def test_state_manager_activities_and_meals(state_manager: StateManager) -> None:
    updated = state_manager.set_fixed_activities({"Monday": ["  Nuoto 18:00 ", ""], "Friday": ["Pizza"]})
    assert updated["Monday"] == ["Nuoto 18:00"]
    assert updated["Friday"] == ["Pizza"]
    assert updated["Tuesday"] == []

    meals = state_manager.set_school_meals(" Pasta al pomodoro ", " Risotto ")
    assert meals["today"] == "Pasta al pomodoro"
    assert meals["tomorrow"] == "Risotto"
    assert meals["updated_at"] is not None


def test_state_manager_cache_ttl(state_manager: StateManager) -> None:
    state_manager.set_cache("weather", {"temp": 20})
    assert state_manager.get_cache("weather", max_age_seconds=60) == {"temp": 20}

    # Backdate cached_at to simulate expiration
    raw = json.loads(state_manager.state_path.read_text(encoding="utf-8"))
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    raw["cache"]["weather"]["cached_at"] = old_ts
    state_manager.state_path.write_text(json.dumps(raw), encoding="utf-8")

    assert state_manager.get_cache("weather", max_age_seconds=60) is None
    assert state_manager.get_cache("weather", max_age_seconds=None) == {"temp": 20}


def test_state_manager_telegram_offset(state_manager: StateManager) -> None:
    assert state_manager.get_telegram_offset() == 0
    state_manager.set_telegram_offset(42)
    assert state_manager.get_telegram_offset() == 42
