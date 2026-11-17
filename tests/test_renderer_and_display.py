"""Unit tests for src/renderer/epaper_ui.py and src/display/waveshare_7in5_b.py."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image

from src.display.waveshare_7in5_b import (
    EPD_HEIGHT,
    EPD_WIDTH,
    Waveshare7in5B,
    compose_preview_image,
)
from src.renderer.epaper_ui import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    get_sample_data,
    get_time_phase,
    render_dashboard,
)


@pytest.mark.parametrize(
    "hour,expected",
    [
        (6, "MATTINA"),
        (11, "MATTINA"),
        (12, "POMERIGGIO"),
        (17, "POMERIGGIO"),
        (18, "SERA"),
        (23, "SERA"),
        (0, "SERA"),
        (5, "SERA"),
    ],
)
def test_get_time_phase(hour: int, expected: str) -> None:
    dt = datetime(2026, 5, 11, hour, 30)
    assert get_time_phase(dt) == expected


@pytest.mark.parametrize("hour", [8, 15, 20])
def test_render_dashboard_outputs_1bit_800x480_buffers(tmp_path: Path, hour: int) -> None:
    dt = datetime(2026, 5, 11, hour, 15)
    sample = get_sample_data(today=dt.date())
    preview = tmp_path / f"preview_{hour}.png"

    black_img, red_img = render_dashboard(sample, preview_path=str(preview), now=dt)

    assert black_img.mode == "1"
    assert black_img.size == (CANVAS_WIDTH, CANVAS_HEIGHT)
    assert red_img.mode == "1"
    assert red_img.size == (CANVAS_WIDTH, CANVAS_HEIGHT)

    # Buffers should contain actual drawn ink (0) as well as background (255)
    assert 0 in black_img.getcolors() or any(c[1] == 0 for c in black_img.getcolors())
    assert any(c[1] == 0 for c in red_img.getcolors())

    assert preview.exists()
    with Image.open(preview) as im:
        assert im.mode == "RGB"
        assert im.size == (800, 480)


def test_render_dashboard_handles_minimal_payload_and_low_battery(tmp_path: Path) -> None:
    dt = datetime(2026, 5, 11, 9, 0)
    minimal = {
        "battery_pct": 15,
        "weather": {"icon": "storm"},
    }
    black_img, red_img = render_dashboard(minimal, preview_path=None, now=dt)
    assert black_img.size == (800, 480)
    assert red_img.size == (800, 480)


def test_waveshare_mock_display_lifecycle(tmp_path: Path) -> None:
    preview = tmp_path / "epd_preview.png"
    black_img = Image.new("1", (EPD_WIDTH, EPD_HEIGHT), 255)
    red_img = Image.new("1", (EPD_WIDTH, EPD_HEIGHT), 255)
    # Draw one black pixel and one red pixel
    black_img.putpixel((10, 10), 0)
    red_img.putpixel((20, 20), 0)

    with Waveshare7in5B(mock=True, preview_path=preview) as epd:
        assert epd.is_mock is True
        saved = epd.display(black_img, red_img)
        assert saved == preview
        assert preview.exists()

    with Image.open(preview) as im:
        assert im.size == (800, 480)
        assert im.mode == "RGB"
        assert im.getpixel((10, 10)) == (15, 15, 15)
        assert im.getpixel((20, 20)) == (205, 32, 32)
        assert im.getpixel((0, 0)) == (255, 255, 255)


def test_waveshare_mock_clear_and_resize(tmp_path: Path) -> None:
    preview = tmp_path / "cleared.png"
    epd = Waveshare7in5B(mock=True, preview_path=preview)
    epd.clear()
    assert preview.exists()

    # Non-standard RGB input should be normalized & composited without error
    small_rgb = Image.new("RGB", (400, 240), (0, 0, 0))
    composed = compose_preview_image(small_rgb, Image.new("1", (800, 480), 255))
    assert composed.size == (800, 480)
    epd.sleep()
