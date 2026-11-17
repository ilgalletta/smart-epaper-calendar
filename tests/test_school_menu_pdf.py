"""Unit tests for Milano Ristorazione PDF + OCR school menu fallback."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
import requests
from PIL import Image, ImageDraw, ImageFont

from src.config import StateManager
from src.fetchers.school_menu_milano import (
    PDF_CACHE_KEY,
    fetch_pdf_menu,
    parse_menu_pdf,
    resolve_school_menu,
)


def _make_image_pdf_bytes(lines: list[str]) -> bytes:
    """Render text lines onto a white image and save as an image-only PDF."""
    img = Image.new("RGB", (1200, 900), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except Exception:
        font = ImageFont.load_default()
    y = 40
    for line in lines:
        draw.text((50, y), line, fill="black", font=font)
        y += 42
    buf = BytesIO()
    img.save(buf, format="PDF", resolution=150.0)
    return buf.getvalue()


def test_parse_menu_pdf_fast_text_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    """parse_menu_pdf uses pypdf text extraction when selectable text is present."""
    sample_text = (
        "Scuola Primaria Pietro Micca - I.C. Statale Gattamelata\n"
        "Lunedi 11/05/2026\n"
        "Primo: Pasta al pomodoro\n"
        "Secondo: Petto di pollo\n"
        "Contorno: Carote julienne\n"
        "Frutta: Mela\n"
        "Martedi 12/05/2026\n"
        "Primo: Risotto allo zafferano\n"
        "Secondo: Platessa al forno\n"
        "Contorno: Insalata verde\n"
        "Frutta: Banana\n"
    )
    fake_page = MagicMock()
    fake_page.extract_text.return_value = sample_text
    fake_reader = MagicMock()
    fake_reader.pages = [fake_page]
    monkeypatch.setattr("pypdf.PdfReader", lambda *a, **kw: fake_reader)

    # Ensure OCR is not invoked when pypdf already extracted a valid menu
    def _fail_ocr(*args, **kwargs):
        raise AssertionError("OCR should not be called when pypdf succeeds")

    monkeypatch.setattr("src.fetchers.school_menu_milano._extract_pdf_text_ocr", _fail_ocr)

    weekly = parse_menu_pdf(b"%PDF-1.4 dummy", school_query="Gattamelata")
    assert weekly["0"] == {
        "primo": "Pasta al pomodoro",
        "secondo": "Petto di pollo",
        "contorno": "Carote julienne",
        "frutta": "Mela",
    }
    assert weekly["1"] == {
        "primo": "Risotto allo zafferano",
        "secondo": "Platessa al forno",
        "contorno": "Insalata verde",
        "frutta": "Banana",
    }


def test_parse_menu_pdf_ocr_fallback_real_image_pdf() -> None:
    """parse_menu_pdf falls back to pypdfium2 + pytesseract OCR on image-only PDFs."""
    pdf_bytes = _make_image_pdf_bytes(
        [
            "Scuola Gattamelata - Menu Settimanale",
            "Lunedi",
            "Primo: Pasta al pomodoro",
            "Secondo: Pollo arrosto",
            "Contorno: Carote",
            "Frutta: Mela",
            "Martedi",
            "Primo: Risotto giallo",
            "Secondo: Pesce al forno",
            "Contorno: Insalata",
            "Frutta: Pera",
        ]
    )

    weekly = parse_menu_pdf(pdf_bytes, school_query="Gattamelata")
    assert "0" in weekly
    assert "Pasta" in weekly["0"]["primo"]
    assert "Pollo" in weekly["0"]["secondo"]
    assert "Carote" in weekly["0"]["contorno"]
    assert "Mela" in weekly["0"]["frutta"]
    assert "1" in weekly
    assert "Risotto" in weekly["1"]["primo"]


def test_fetch_pdf_menu_url_local_and_cache(
    tmp_path: Path,
    state_manager: StateManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fetch_pdf_menu downloads from pdf_url, caches in StateManager, and supports pdf_path."""
    now = datetime(2026, 5, 11, 8, 0, tzinfo=ZoneInfo("Europe/Rome"))  # Monday
    sample_text = (
        "Lunedi\n"
        "Primo: Pasta al pesto\n"
        "Secondo: Polpette\n"
        "Contorno: Zucchine\n"
        "Frutta: Arancia\n"
        "Martedi\n"
        "Primo: Minestrone\n"
        "Secondo: Frittata\n"
        "Contorno: Patate\n"
        "Frutta: Mela\n"
    )
    fake_page = MagicMock()
    fake_page.extract_text.return_value = sample_text
    fake_reader = MagicMock()
    fake_reader.pages = [fake_page]
    monkeypatch.setattr("pypdf.PdfReader", lambda *a, **kw: fake_reader)

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.content = b"%PDF-1.4 fake"
    monkeypatch.setattr(
        "src.fetchers.school_menu_milano.requests.get",
        lambda *a, **kw: mock_resp,
    )

    cfg = {
        "timezone": "Europe/Rome",
        "milanoristorazione": {
            "enabled": True,
            "school_query": "Gattamelata",
            "pdf_url": "https://example.com/menu.pdf",
            "pdf_path": "",
            "cache_ttl_seconds": 3600,
        },
    }
    res = fetch_pdf_menu(config=cfg, state_manager=state_manager, now=now)
    assert res["source"] == "pdf_url"
    assert res["today"]["primo"] == "Pasta al pesto"
    assert res["tomorrow"]["primo"] == "Minestrone"
    assert state_manager.get_cache(PDF_CACHE_KEY) is not None

    # Subsequent call hits fresh cache even if requests.get fails
    monkeypatch.setattr(
        "src.fetchers.school_menu_milano.requests.get",
        MagicMock(side_effect=requests.ConnectionError("offline")),
    )
    cached_res = fetch_pdf_menu(config=cfg, state_manager=state_manager, now=now)
    assert cached_res["source"] == "pdf_cache"
    assert cached_res["today"]["primo"] == "Pasta al pesto"

    # Local pdf_path with a fresh StateManager
    local_pdf = tmp_path / "menu_scuola.pdf"
    local_pdf.write_bytes(b"%PDF-1.4 local")
    fresh_sm = StateManager(state_path=tmp_path / "fresh_state.json")
    local_cfg = {
        "timezone": "Europe/Rome",
        "milanoristorazione": {
            "enabled": True,
            "pdf_url": "",
            "pdf_path": str(local_pdf),
        },
    }
    local_res = fetch_pdf_menu(config=local_cfg, state_manager=fresh_sm, now=now)
    assert local_res["source"] == "pdf_path"
    assert local_res["today"]["primo"] == "Pasta al pesto"


def test_resolve_school_menu_fallback_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify 4-tier fallback: state.json -> live HTML/JSON -> PDF+OCR -> config.yaml."""
    now = datetime(2026, 5, 11, 8, 0, tzinfo=ZoneInfo("Europe/Rome"))  # Monday
    sm = StateManager(state_path=tmp_path / "state.json")

    cfg = {
        "timezone": "Europe/Rome",
        "milanoristorazione": {
            "enabled": True,
            "menu_url": "https://www.milanoristorazione.it/il-menu-del-giorno",
            "pdf_url": "https://example.com/menu.pdf",
            "pdf_path": "",
        },
        "school_menu": {
            "week_1": {
                "monday": "Static Monday",
                "tuesday": "Static Tuesday",
            }
        },
    }

    # 1. Manual Web UI override wins over everything
    override = resolve_school_menu(
        {"today": "Manual Today", "tomorrow": "Manual Tomorrow"},
        cfg,
        now,
        state_manager=sm,
    )
    assert override == {"today": "Manual Today", "tomorrow": "Manual Tomorrow"}

    # 2. Live HTML/JSON wins over PDF and static config
    monkeypatch.setattr(
        "src.fetchers.school_menu_milano.fetch_milanoristorazione_menu",
        lambda **kw: {"today": "Live Today", "tomorrow": "Live Tomorrow", "source": "live"},
    )
    live = resolve_school_menu({}, cfg, now, state_manager=sm)
    assert live == {"today": "Live Today", "tomorrow": "Live Tomorrow"}

    # 3. PDF + OCR fallback when live HTML/JSON returns empty
    monkeypatch.setattr(
        "src.fetchers.school_menu_milano.fetch_milanoristorazione_menu",
        lambda **kw: {"today": "", "tomorrow": "", "source": "none"},
    )
    monkeypatch.setattr(
        "src.fetchers.school_menu_milano.fetch_pdf_menu",
        lambda **kw: {
            "today": {"primo": "PDF Primo", "secondo": "", "contorno": "", "frutta": ""},
            "tomorrow": {"primo": "PDF Domani", "secondo": "", "contorno": "", "frutta": ""},
            "source": "pdf_url",
        },
    )
    pdf_fallback = resolve_school_menu({}, cfg, now, state_manager=sm)
    assert pdf_fallback["today"]["primo"] == "PDF Primo"
    assert pdf_fallback["tomorrow"]["primo"] == "PDF Domani"

    # 4. Static config.yaml fallback when both live and PDF return empty
    monkeypatch.setattr(
        "src.fetchers.school_menu_milano.fetch_pdf_menu",
        lambda **kw: {"today": "", "tomorrow": "", "source": "none"},
    )
    static_fallback = resolve_school_menu({}, cfg, now, state_manager=sm)
    assert static_fallback == {"today": "Static Monday", "tomorrow": "Static Tuesday"}
