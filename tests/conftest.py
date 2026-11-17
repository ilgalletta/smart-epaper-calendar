"""Shared pytest fixtures for Smart E-Paper Calendar tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import StateManager, save_config
from src.web_ui import create_app


@pytest.fixture
def tmp_state_path(tmp_path: Path) -> Path:
    return tmp_path / "data" / "state.json"


@pytest.fixture
def state_manager(tmp_state_path: Path) -> StateManager:
    return StateManager(state_path=tmp_state_path)


@pytest.fixture
def tmp_config_path(tmp_path: Path) -> Path:
    cfg_path = tmp_path / "config.yaml"
    save_config(
        {
            "timezone": "Europe/Rome",
            "calendars": [
                {"name": "Family", "url": "https://example.com/family.ics"},
            ],
            "weather": {
                "latitude": 45.4642,
                "longitude": 9.1900,
                "location_name": "Milano",
            },
            "commute": {
                "home_address": "Via Roma 1, Milano",
                "office_address": "Piazza Duomo, Milano",
            },
            "news": {
                "feed_url": "https://www.ilpost.it/feed/",
                "max_items": 3,
            },
            "web_ui": {
                "host": "127.0.0.1",
                "port": 8080,
                "password": "test-password",
                "session_secret": "test-session-secret-123456",
                "preview_image_path": str(tmp_path / "data" / "preview.png"),
                "refresh_command": "",
            },
        },
        config_path=cfg_path,
    )
    return cfg_path


@pytest.fixture
def web_client(tmp_config_path: Path, state_manager: StateManager) -> TestClient:
    app = create_app(config_path=tmp_config_path, state_manager=state_manager)
    return TestClient(app)
