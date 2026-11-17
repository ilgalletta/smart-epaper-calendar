"""
Production 800x480 3-Color (Black / White / Red) Pillow renderer
for Waveshare 7.5" e-Paper HAT (B) smart calendar.

Outputs two 1-bit ("1") Pillow images:
  - black_img: 0 = black ink, 255 = white/blank
  - red_img:   0 = red ink,   255 = white/blank
And optionally saves a combined RGB preview PNG (e.g. data/preview.png)
for the LAN Remote Web UI.
"""

from __future__ import annotations

import os
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

CANVAS_WIDTH = 800
CANVAS_HEIGHT = 480

# Colors for 1-bit ("1") e-paper buffers
INK_ON = 0
INK_OFF = 255

# Colors for combined RGB preview
PREVIEW_WHITE = (252, 252, 250)
PREVIEW_BLACK = (20, 20, 20)
PREVIEW_RED = (200, 32, 32)

ITALIAN_DAYS_FULL = [
    "LUNEDÌ",
    "MARTEDÌ",
    "MERCOLEDÌ",
    "GIOVEDÌ",
    "VENERDÌ",
    "SABATO",
    "DOMENICA",
]
ITALIAN_DAYS_SHORT = ["LUN", "MAR", "MER", "GIO", "VEN", "SAB", "DOM"]
ITALIAN_MONTHS = [
    "",
    "GENNAIO",
    "FEBBRAIO",
    "MARZO",
    "APRILE",
    "MAGGIO",
    "GIUGNO",
    "LUGLIO",
    "AGOSTO",
    "SETTEMBRE",
    "OTTOBRE",
    "NOVEMBRE",
    "DICEMBRE",
]
ITALIAN_MONTHS_SHORT = [
    "",
    "GEN",
    "FEB",
    "MAR",
    "APR",
    "MAG",
    "GIU",
    "LUG",
    "AGO",
    "SET",
    "OTT",
    "NOV",
    "DIC",
]


def _find_font_path(candidates: List[str]) -> Optional[str]:
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


class FontPalette:
    """Loads crisp DejaVu/Liberation TTF fonts with safe fallback to default."""

    def __init__(self) -> None:
        sans_regular_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        ]
        sans_bold_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        ]
        mono_bold_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
        ]

        self.regular_path = _find_font_path(sans_regular_candidates)
        self.bold_path = _find_font_path(sans_bold_candidates) or self.regular_path
        self.mono_bold_path = _find_font_path(mono_bold_candidates) or self.bold_path

        self.title_lg = self._load(self.bold_path, 20)
        self.header = self._load(self.bold_path, 15)
        self.subhead = self._load(self.bold_path, 13)
        self.body = self._load(self.regular_path, 13)
        self.body_bold = self._load(self.bold_path, 13)
        self.small = self._load(self.regular_path, 11)
        self.small_bold = self._load(self.bold_path, 11)
        self.tiny = self._load(self.bold_path, 10)
        self.temp_lg = self._load(self.bold_path, 30)
        self.metric_lg = self._load(self.bold_path, 24)
        self.mono_sm = self._load(self.mono_bold_path, 11)

    @staticmethod
    def _load(path: Optional[str], size: int) -> ImageFont.ImageFont:
        if path:
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
        return ImageFont.load_default()


def get_time_phase(now: Optional[datetime] = None) -> str:
    """
    Determine active Time-of-Day phase:
      - 06:00–11:59 -> MATTINA
      - 12:00–17:59 -> POMERIGGIO
      - 18:00–23:59 (and 00:00–05:59) -> SERA
    """
    dt = now or datetime.now()
    hour = dt.hour
    if 6 <= hour < 12:
        return "MATTINA"
    if 12 <= hour < 18:
        return "POMERIGGIO"
    return "SERA"


class EPaperRenderer:
    """
    800x480 3-Color (Black / White / Red) Pillow renderer for Waveshare 7.5" HAT (B).
    """

    def __init__(self) -> None:
        self.width = CANVAS_WIDTH
        self.height = CANVAS_HEIGHT
        self.fonts = FontPalette()

    def render(
        self,
        data: Dict[str, Any],
        now: Optional[datetime] = None,
        preview_path: Optional[str] = "data/preview.png",
    ) -> Tuple[Image.Image, Image.Image]:
        """
        Render the dashboard into (black_img, red_img) 1-bit Pillow images.
        If preview_path is provided, also writes a combined RGB PNG for the Web UI.
        """
        dt = now or datetime.now()
        phase = data.get("phase") or get_time_phase(dt)

        black_img = Image.new("1", (self.width, self.height), INK_OFF)
        red_img = Image.new("1", (self.width, self.height), INK_OFF)

        draw_b = ImageDraw.Draw(black_img)
        draw_r = ImageDraw.Draw(red_img)
        draw_b.fontmode = "1"
        draw_r.fontmode = "1"

        # Layout coordinates
        top_h = 44
        split_x = 480  # 60% left, 40% right

        # 1. Top Bar
        self._draw_top_bar(draw_b, draw_r, dt, phase, data, top_h)

        # Vertical divider between left & right columns
        draw_b.line([(split_x, top_h), (split_x, self.height)], fill=INK_ON, width=2)

        # 2. Left Column: Week Calendar (top) + Fixed Weekly Activities (bottom)
        fixed_h = 96
        cal_bottom = self.height - fixed_h
        self._draw_week_calendar(
            draw_b, draw_r, dt.date(), data.get("calendar_days", []), 0, top_h, split_x, cal_bottom
        )
        self._draw_fixed_activities(
            draw_b,
            draw_r,
            dt.date(),
            data.get("fixed_activities", []),
            0,
            cal_bottom,
            split_x,
            self.height,
        )

        # 3. Right Column: Mensa Scuola (top) + 3-slot stack (bottom)
        mensa_bottom = 166
        self._draw_mensa(
            draw_b,
            draw_r,
            phase,
            data.get("mensa", {}),
            split_x + 2,
            top_h,
            self.width,
            mensa_bottom,
        )

        # Bottom 3-slot stack: 314px total -> Slot 1 (96px), Slot 2 (109px), Slot 3 (109px)
        slot1_bottom = 262
        slot2_bottom = 371
        slot3_bottom = self.height

        # Slot 1: Meteo Locale (always visible)
        self._draw_meteo(
            draw_b,
            draw_r,
            data.get("weather", {}),
            split_x + 2,
            mensa_bottom,
            self.width,
            slot1_bottom,
        )

        # Slot 2 & Slot 3: Dynamic Time-of-Day widgets
        if phase == "MATTINA":
            self._draw_time_to_work(
                draw_b,
                draw_r,
                data.get("commute", {}),
                split_x + 2,
                slot1_bottom,
                self.width,
                slot2_bottom,
            )
            self._draw_ilpost(
                draw_b,
                draw_r,
                data.get("news", []),
                split_x + 2,
                slot2_bottom,
                self.width,
                slot3_bottom,
            )
        elif phase == "POMERIGGIO":
            self._draw_ilpost(
                draw_b,
                draw_r,
                data.get("news", []),
                split_x + 2,
                slot1_bottom,
                self.width,
                slot2_bottom,
            )
            self._draw_grocery_list(
                draw_b,
                draw_r,
                data.get("grocery", []),
                split_x + 2,
                slot2_bottom,
                self.width,
                slot3_bottom,
            )
        else:  # SERA
            self._draw_grocery_list(
                draw_b,
                draw_r,
                data.get("grocery", []),
                split_x + 2,
                slot1_bottom,
                self.width,
                slot2_bottom,
            )
            self._draw_ilpost(
                draw_b,
                draw_r,
                data.get("news", []),
                split_x + 2,
                slot2_bottom,
                self.width,
                slot3_bottom,
            )

        if preview_path:
            self.save_preview(black_img, red_img, preview_path)

        return black_img, red_img

    @staticmethod
    def combine_preview(black_img: Image.Image, red_img: Image.Image) -> Image.Image:
        """Combine 1-bit black and red buffers into a crisp RGB preview image."""
        preview = Image.new("RGB", black_img.size, PREVIEW_WHITE)
        b_mask = black_img.point(lambda p: 255 if p == 0 else 0, mode="L")
        r_mask = red_img.point(lambda p: 255 if p == 0 else 0, mode="L")
        preview.paste(PREVIEW_BLACK, (0, 0), b_mask)
        preview.paste(PREVIEW_RED, (0, 0), r_mask)
        return preview

    @classmethod
    def save_preview(
        cls, black_img: Image.Image, red_img: Image.Image, preview_path: str
    ) -> Path:
        out_path = Path(preview_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        preview = cls.combine_preview(black_img, red_img)
        preview.save(out_path, format="PNG")
        return out_path

    # ------------------------------------------------------------------
    # Drawing Helpers
    # ------------------------------------------------------------------
    def _truncate(
        self, draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int
    ) -> str:
        if max_width <= 0:
            return ""
        if self._text_width(draw, text, font) <= max_width:
            return text
        ellipsis = "..."
        trimmed = text
        while trimmed and self._text_width(draw, trimmed + ellipsis, font) > max_width:
            trimmed = trimmed[:-1]
        return (trimmed + ellipsis) if trimmed else ""

    @staticmethod
    def _text_width(
        draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont
    ) -> int:
        bbox = draw.textbbox((0, 0), text, font=font)
        return int(bbox[2] - bbox[0])

    @staticmethod
    def _text_height(
        draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont
    ) -> int:
        bbox = draw.textbbox((0, 0), text, font=font)
        return int(bbox[3] - bbox[1])

    def _draw_pill(
        self,
        draw: ImageDraw.ImageDraw,
        xy: Tuple[int, int, int, int],
        text: str,
        font: ImageFont.ImageFont,
        filled: bool = True,
        radius: int = 4,
    ) -> None:
        x1, y1, x2, y2 = xy
        if filled:
            draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=INK_ON)
            text_fill = INK_OFF
        else:
            draw.rounded_rectangle(
                [x1, y1, x2, y2], radius=radius, outline=INK_ON, width=2
            )
            text_fill = INK_ON

        tw = self._text_width(draw, text, font)
        th = self._text_height(draw, text, font)
        tx = x1 + max(0, (x2 - x1 - tw) // 2)
        ty = y1 + max(0, (y2 - y1 - th) // 2) - 1
        draw.text((tx, ty), text, font=font, fill=text_fill)

    # ------------------------------------------------------------------
    # Section 1: Top Bar
    # ------------------------------------------------------------------
    def _draw_top_bar(
        self,
        draw_b: ImageDraw.ImageDraw,
        draw_r: ImageDraw.ImageDraw,
        dt: datetime,
        phase: str,
        data: Dict[str, Any],
        height: int,
    ) -> None:
        # Bottom border
        draw_b.line([(0, height - 2), (self.width, height - 2)], fill=INK_ON, width=2)

        # Left: Current Date
        day_name = ITALIAN_DAYS_FULL[dt.weekday()]
        month_name = ITALIAN_MONTHS[dt.month]
        date_str = f"{day_name} {dt.day} {month_name} {dt.year}"
        draw_b.text((14, 11), date_str, font=self.fonts.title_lg, fill=INK_ON)

        # Phase badge (Red for MATTINA / SERA, Black for POMERIGGIO, or always Red accent)
        phase_w = self._text_width(draw_r, phase, self.fonts.subhead) + 20
        phase_x1 = 480 - phase_w - 12
        self._draw_pill(
            draw_r,
            (phase_x1, 9, phase_x1 + phase_w, height - 11),
            phase,
            self.fonts.subhead,
            filled=True,
            radius=4,
        )

        # Right: Sync time + Battery/Status indicator
        last_sync = data.get("last_sync") or dt.strftime("%H:%M")
        sync_label = f"SYNC {last_sync}"
        draw_b.text((494, 14), sync_label, font=self.fonts.small_bold, fill=INK_ON)

        battery = data.get("battery_pct")
        status_text = data.get("status", "ONLINE")

        # Draw battery icon on far right
        bx = self.width - 66
        by = 13
        bw, bh = 30, 16
        draw_b.rectangle([bx, by, bx + bw, by + bh], outline=INK_ON, width=2)
        draw_b.rectangle([bx + bw, by + 4, bx + bw + 3, by + bh - 4], fill=INK_ON)

        if isinstance(battery, (int, float)):
            pct = max(0, min(100, int(battery)))
            fill_w = int((bw - 6) * (pct / 100.0))
            target_draw = draw_r if pct <= 20 else draw_b
            if fill_w > 0:
                target_draw.rectangle(
                    [bx + 3, by + 3, bx + 3 + fill_w, by + bh - 3], fill=INK_ON
                )
            pct_str = f"{pct}%"
            pw = self._text_width(draw_b, pct_str, self.fonts.small_bold)
            draw_b.text((bx - pw - 6, 14), pct_str, font=self.fonts.small_bold, fill=INK_ON)
            # Status dot
            draw_b.text((self.width - 28, 14), "OK", font=self.fonts.tiny, fill=INK_ON)
        else:
            # AC / Always-on indicator
            draw_b.rectangle([bx + 4, by + 4, bx + bw - 4, by + bh - 4], fill=INK_ON)
            sw = self._text_width(draw_b, status_text, self.fonts.small_bold)
            draw_b.text(
                (bx - sw - 8, 14), status_text, font=self.fonts.small_bold, fill=INK_ON
            )

    # ------------------------------------------------------------------
    # Section 2: Left Column - Week Calendar (7 days)
    # ------------------------------------------------------------------
    def _draw_week_calendar(
        self,
        draw_b: ImageDraw.ImageDraw,
        draw_r: ImageDraw.ImageDraw,
        today: date,
        calendar_days: List[Dict[str, Any]],
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> None:
        # Header strip
        header_h = 28
        draw_b.rectangle([x1, y1, x2 - 2, y1 + header_h], fill=INK_ON)
        draw_b.text(
            (x1 + 12, y1 + 6),
            "CALENDARIO SETTIMANALE",
            font=self.fonts.subhead,
            fill=INK_OFF,
        )

        # Build 7-day map starting from Monday of current week (or today if provided)
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        range_str = (
            f"{monday.day} {ITALIAN_MONTHS_SHORT[monday.month]} – "
            f"{sunday.day} {ITALIAN_MONTHS_SHORT[sunday.month]}"
        )
        rw = self._text_width(draw_b, range_str, self.fonts.small_bold)
        draw_b.text((x2 - rw - 12, y1 + 7), range_str, font=self.fonts.small_bold, fill=INK_OFF)

        events_by_date: Dict[str, List[Dict[str, Any]]] = {}
        for day_entry in calendar_days:
            d_key = str(day_entry.get("date", ""))
            events_by_date[d_key] = day_entry.get("events", [])

        body_top = y1 + header_h
        row_h = (y2 - body_top) // 7  # ~44px per day

        for idx in range(7):
            cur_date = monday + timedelta(days=idx)
            cur_iso = cur_date.isoformat()
            is_today = cur_date == today
            ry1 = body_top + idx * row_h
            ry2 = ry1 + row_h if idx < 6 else y2

            # Row divider
            if idx > 0:
                draw_b.line([(x1 + 8, ry1), (x2 - 8, ry1)], fill=INK_ON, width=1)

            # Date badge column (left 76px)
            badge_x1 = x1 + 10
            badge_y1 = ry1 + 5
            badge_x2 = x1 + 78
            badge_y2 = ry2 - 5

            day_abbr = ITALIAN_DAYS_SHORT[cur_date.weekday()]
            day_num = f"{cur_date.day:02d}"

            if is_today:
                # Highlight today in Red!
                draw_r.rounded_rectangle(
                    [badge_x1, badge_y1, badge_x2, badge_y2], radius=4, fill=INK_ON
                )
                # Subtle red accent bar on right edge of badge / top border
                draw_r.rectangle([x1, ry1 + 1, x1 + 4, ry2 - 1], fill=INK_ON)
                draw_r.text(
                    (badge_x1 + 8, badge_y1 + 4),
                    day_abbr,
                    font=self.fonts.small_bold,
                    fill=INK_OFF,
                )
                draw_r.text(
                    (badge_x1 + 8, badge_y1 + 17),
                    day_num,
                    font=self.fonts.header,
                    fill=INK_OFF,
                )
            else:
                draw_b.rounded_rectangle(
                    [badge_x1, badge_y1, badge_x2, badge_y2],
                    radius=4,
                    outline=INK_ON,
                    width=1,
                )
                draw_b.text(
                    (badge_x1 + 8, badge_y1 + 4),
                    day_abbr,
                    font=self.fonts.small_bold,
                    fill=INK_ON,
                )
                draw_b.text(
                    (badge_x1 + 8, badge_y1 + 17),
                    day_num,
                    font=self.fonts.header,
                    fill=INK_ON,
                )

            # Events list for this day
            day_events = events_by_date.get(cur_iso, [])
            ev_x = badge_x2 + 12
            max_ev_w = x2 - ev_x - 10

            if not day_events:
                draw_b.text(
                    (ev_x, ry1 + (row_h // 2) - 7),
                    "— Nessun impegno",
                    font=self.fonts.small,
                    fill=INK_ON,
                )
            else:
                # Show up to 2 events cleanly per row
                visible_events = day_events[:2]
                extra_count = len(day_events) - len(visible_events)
                for e_idx, ev in enumerate(visible_events):
                    ey = ry1 + 5 + e_idx * 18
                    ev_time = ev.get("time", "")
                    ev_title = ev.get("title", "")
                    is_important = bool(ev.get("important", False))

                    if ev_time:
                        time_str = f"{ev_time}"
                        tw = self._text_width(draw_b, time_str, self.fonts.mono_sm)
                        t_draw = draw_r if (is_today or is_important) else draw_b
                        t_draw.text(
                            (ev_x, ey + 1), time_str, font=self.fonts.mono_sm, fill=INK_ON
                        )
                        title_x = ev_x + tw + 8
                    else:
                        # All-day bullet
                        bullet_draw = draw_r if (is_today or is_important) else draw_b
                        bullet_draw.ellipse([ev_x, ey + 4, ev_x + 6, ey + 10], fill=INK_ON)
                        title_x = ev_x + 12

                    avail_w = x2 - title_x - (44 if (extra_count > 0 and e_idx == 1) else 10)
                    title_font = self.fonts.body_bold if is_today else self.fonts.body
                    trunc_title = self._truncate(draw_b, ev_title, title_font, avail_w)
                    draw_b.text((title_x, ey), trunc_title, font=title_font, fill=INK_ON)

                if extra_count > 0:
                    more_str = f"+{extra_count}"
                    mw = self._text_width(draw_r, more_str, self.fonts.small_bold)
                    draw_r.text(
                        (x2 - mw - 10, ry1 + 23),
                        more_str,
                        font=self.fonts.small_bold,
                        fill=INK_ON,
                    )

    # ------------------------------------------------------------------
    # Section 3: Left Column Bottom - Fixed Weekly Activities
    # ------------------------------------------------------------------
    def _draw_fixed_activities(
        self,
        draw_b: ImageDraw.ImageDraw,
        draw_r: ImageDraw.ImageDraw,
        today: date,
        activities: List[Dict[str, Any]],
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> None:
        draw_b.line([(x1, y1), (x2, y1)], fill=INK_ON, width=2)
        draw_b.text(
            (x1 + 12, y1 + 7),
            "ATTIVITÀ FISSE SETTIMANALI",
            font=self.fonts.subhead,
            fill=INK_ON,
        )

        if not activities:
            draw_b.text(
                (x1 + 12, y1 + 34),
                "Nessuna attività fissa configurata.",
                font=self.fonts.body,
                fill=INK_ON,
            )
            return

        today_abbr = ITALIAN_DAYS_SHORT[today.weekday()]
        # 2-column grid, up to 4 items
        col_w = (x2 - x1 - 24) // 2
        start_y = y1 + 30
        row_h = 28

        for idx, act in enumerate(activities[:4]):
            col = idx % 2
            row = idx // 2
            ax = x1 + 12 + col * (col_w + 6)
            ay = start_y + row * row_h

            days_label = str(act.get("days", "")).upper()
            time_label = str(act.get("time", ""))
            title = str(act.get("title", ""))
            is_today_act = today_abbr in days_label

            # Day/Time pill
            prefix = f"{days_label} {time_label}".strip()
            pw = self._text_width(draw_b, prefix, self.fonts.tiny) + 10
            pill_draw = draw_r if is_today_act else draw_b
            self._draw_pill(
                pill_draw,
                (ax, ay + 2, ax + pw, ay + 20),
                prefix,
                self.fonts.tiny,
                filled=is_today_act,
                radius=3,
            )

            tx = ax + pw + 6
            avail_w = (ax + col_w) - tx - 4
            font = self.fonts.small_bold if is_today_act else self.fonts.small
            trunc = self._truncate(draw_b, title, font, avail_w)
            draw_b.text((tx, ay + 4), trunc, font=font, fill=INK_ON)

    # ------------------------------------------------------------------
    # Section 4: Right Column Top - Mensa Scuola
    # ------------------------------------------------------------------
    def _draw_mensa(
        self,
        draw_b: ImageDraw.ImageDraw,
        draw_r: ImageDraw.ImageDraw,
        phase: str,
        mensa: Dict[str, Any],
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> None:
        draw_b.line([(x1, y2), (x2, y2)], fill=INK_ON, width=2)

        # Header
        draw_b.text((x1 + 12, y1 + 8), "MENSA SCUOLA", font=self.fonts.header, fill=INK_ON)

        is_evening = phase == "SERA"
        badge_label = "DOMANI" if is_evening else "OGGI"
        bw = self._text_width(draw_r, badge_label, self.fonts.tiny) + 14
        self._draw_pill(
            draw_r if is_evening else draw_b,
            (x2 - bw - 12, y1 + 7, x2 - 12, y1 + 25),
            badge_label,
            self.fonts.tiny,
            filled=True,
            radius=3,
        )

        # Pick today's or tomorrow's menu if nested, or flat dict
        if is_evening and "tomorrow" in mensa:
            menu = mensa["tomorrow"]
        elif not is_evening and "today" in mensa:
            menu = mensa["today"]
        else:
            menu = mensa

        if isinstance(menu, str):
            parts = [p.strip() for p in menu.split(",") if p.strip()]
            courses = [
                ("Primo", parts[0] if len(parts) > 0 else "—"),
                ("Secondo", parts[1] if len(parts) > 1 else "—"),
                ("Contorno", parts[2] if len(parts) > 2 else "—"),
                ("Frutta", parts[3] if len(parts) > 3 else "—"),
            ]
        elif isinstance(menu, dict):
            courses = [
                ("Primo", menu.get("primo", "—")),
                ("Secondo", menu.get("secondo", "—")),
                ("Contorno", menu.get("contorno", "—")),
                ("Frutta", menu.get("frutta", "—")),
            ]
        else:
            courses = [
                ("Primo", "—"),
                ("Secondo", "—"),
                ("Contorno", "—"),
                ("Frutta", "—"),
            ]

        cy = y1 + 32
        for label, dish in courses:
            label_str = f"{label}:"
            draw_b.text((x1 + 12, cy), label_str, font=self.fonts.small_bold, fill=INK_ON)
            lw = self._text_width(draw_b, label_str, self.fonts.small_bold)
            dx = x1 + 18 + lw
            avail_w = x2 - dx - 10
            trunc_dish = self._truncate(draw_b, str(dish), self.fonts.body, avail_w)
            draw_b.text((dx, cy - 1), trunc_dish, font=self.fonts.body, fill=INK_ON)
            cy += 21

    # ------------------------------------------------------------------
    # Section 5: Right Column Slot 1 - Meteo Locale
    # ------------------------------------------------------------------
    def _draw_meteo(
        self,
        draw_b: ImageDraw.ImageDraw,
        draw_r: ImageDraw.ImageDraw,
        weather: Dict[str, Any],
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> None:
        draw_b.line([(x1, y2), (x2, y2)], fill=INK_ON, width=2)

        city = weather.get("city", "METEO LOCALE").upper()
        draw_b.text((x1 + 12, y1 + 6), city, font=self.fonts.subhead, fill=INK_ON)

        condition = weather.get("condition", "Sereno")
        icon_type = weather.get("icon", "partly_cloudy")
        temp = weather.get("temp", "--")
        t_min = weather.get("temp_min", "--")
        t_max = weather.get("temp_max", "--")

        # Draw crisp vector weather icon on left
        self._draw_weather_icon(draw_b, draw_r, icon_type, x1 + 18, y1 + 30)

        # Temperature
        temp_str = f"{temp}°"
        draw_b.text((x1 + 78, y1 + 26), temp_str, font=self.fonts.temp_lg, fill=INK_ON)

        # Condition + Min/Max on right
        rx = x1 + 158
        avail_w = x2 - rx - 10
        cond_trunc = self._truncate(draw_b, str(condition), self.fonts.body_bold, avail_w)
        draw_b.text((rx, y1 + 30), cond_trunc, font=self.fonts.body_bold, fill=INK_ON)

        min_str = f"MIN {t_min}°"
        max_str = f"MAX {t_max}°"
        draw_b.text((rx, y1 + 52), min_str, font=self.fonts.small_bold, fill=INK_ON)
        mw = self._text_width(draw_b, min_str, self.fonts.small_bold)
        draw_r.text((rx + mw + 12, y1 + 52), max_str, font=self.fonts.small_bold, fill=INK_ON)

    def _draw_weather_icon(
        self,
        draw_b: ImageDraw.ImageDraw,
        draw_r: ImageDraw.ImageDraw,
        icon_type: str,
        x: int,
        y: int,
    ) -> None:
        """Draws a 44x44 crisp 2-color (black+red) vector weather icon."""
        if icon_type in ("sun", "clear"):
            draw_r.ellipse([x + 12, y + 12, x + 32, y + 32], fill=INK_ON)
            # Rays
            rays = [
                ((x + 22, y + 2), (x + 22, y + 8)),
                ((x + 22, y + 36), (x + 22, y + 42)),
                ((x + 2, y + 22), (x + 8, y + 22)),
                ((x + 36, y + 22), (x + 42, y + 22)),
                ((x + 8, y + 8), (x + 12, y + 12)),
                ((x + 32, y + 32), (x + 36, y + 36)),
                ((x + 36, y + 8), (x + 32, y + 12)),
                ((x + 12, y + 32), (x + 8, y + 36)),
            ]
            for p1, p2 in rays:
                draw_r.line([p1, p2], fill=INK_ON, width=2)
        elif icon_type in ("partly_cloudy", "sun_cloud"):
            # Sun behind cloud
            draw_r.ellipse([x + 20, y + 4, x + 36, y + 20], fill=INK_ON)
            # Cloud outline
            draw_b.rounded_rectangle(
                [x + 4, y + 18, x + 36, y + 36], radius=8, fill=INK_OFF, outline=INK_ON, width=2
            )
            draw_b.ellipse([x + 10, y + 12, x + 26, y + 28], fill=INK_OFF, outline=INK_ON, width=2)
            draw_b.rectangle([x + 10, y + 20, x + 28, y + 34], fill=INK_OFF)
        elif icon_type in ("rain", "showers"):
            draw_b.rounded_rectangle(
                [x + 4, y + 8, x + 38, y + 26], radius=8, outline=INK_ON, width=2
            )
            for rx in (x + 11, x + 21, x + 31):
                draw_b.line([(rx, y + 30), (rx - 3, y + 40)], fill=INK_ON, width=2)
        elif icon_type in ("storm", "thunder"):
            draw_b.rounded_rectangle(
                [x + 4, y + 6, x + 38, y + 24], radius=8, outline=INK_ON, width=2
            )
            draw_r.polygon(
                [(x + 22, y + 24), (x + 15, y + 34), (x + 21, y + 34), (x + 17, y + 43), (x + 28, y + 31), (x + 22, y + 31)],
                fill=INK_ON,
            )
        else:  # cloudy / fog
            draw_b.rounded_rectangle(
                [x + 4, y + 14, x + 38, y + 34], radius=9, outline=INK_ON, width=2
            )
            draw_b.ellipse([x + 12, y + 8, x + 28, y + 24], fill=INK_OFF, outline=INK_ON, width=2)
            draw_b.rectangle([x + 12, y + 16, x + 30, y + 32], fill=INK_OFF)

    # ------------------------------------------------------------------
    # Section 6: Dynamic Widget - Time to Work (Morning)
    # ------------------------------------------------------------------
    def _draw_time_to_work(
        self,
        draw_b: ImageDraw.ImageDraw,
        draw_r: ImageDraw.ImageDraw,
        commute: Dict[str, Any],
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> None:
        draw_b.line([(x1, y2), (x2, y2)], fill=INK_ON, width=2)

        # Red/Black badge header
        draw_b.text((x1 + 12, y1 + 8), "TIME TO WORK", font=self.fonts.subhead, fill=INK_ON)
        status = str(commute.get("traffic_status", "REGOLARE")).upper()
        is_delay = any(k in status for k in ("TRAFFICO", "RITARDO", "CODA", "LENTO"))
        sw = self._text_width(draw_r, status, self.fonts.tiny) + 14
        self._draw_pill(
            draw_r if is_delay else draw_b,
            (x2 - sw - 12, y1 + 7, x2 - 12, y1 + 25),
            status,
            self.fonts.tiny,
            filled=True,
            radius=3,
        )

        # Large duration in Red/Black badge
        mins = commute.get("duration_min", 25)
        dur_str = f"{mins} min"
        dw = self._text_width(draw_r, dur_str, self.fonts.metric_lg) + 22
        self._draw_pill(
            draw_r,
            (x1 + 12, y1 + 36, x1 + 12 + dw, y1 + 78),
            dur_str,
            self.fonts.metric_lg,
            filled=True,
            radius=6,
        )

        # Route & ETA details
        rx = x1 + 12 + dw + 12
        avail_w = x2 - rx - 10
        route = self._truncate(
            draw_b, str(commute.get("route", "Percorso standard")), self.fonts.body_bold, avail_w
        )
        eta = self._truncate(
            draw_b, str(commute.get("eta_note", "Arrivo stimato in orario")), self.fonts.small, avail_w
        )
        draw_b.text((rx, y1 + 39), route, font=self.fonts.body_bold, fill=INK_ON)
        draw_b.text((rx, y1 + 60), eta, font=self.fonts.small, fill=INK_ON)

    # ------------------------------------------------------------------
    # Section 7: Dynamic Widget - ilPost.it Headlines
    # ------------------------------------------------------------------
    def _draw_ilpost(
        self,
        draw_b: ImageDraw.ImageDraw,
        draw_r: ImageDraw.ImageDraw,
        news: List[str],
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> None:
        if y2 < self.height:
            draw_b.line([(x1, y2), (x2, y2)], fill=INK_ON, width=2)

        # Header with ilPost.it red tag
        draw_b.text((x1 + 12, y1 + 7), "ULTIME NOTIZIE", font=self.fonts.subhead, fill=INK_ON)
        tag = "ilPost.it"
        tw = self._text_width(draw_r, tag, self.fonts.tiny) + 12
        self._draw_pill(
            draw_r,
            (x2 - tw - 12, y1 + 6, x2 - 12, y1 + 24),
            tag,
            self.fonts.tiny,
            filled=True,
            radius=3,
        )

        if not news:
            draw_b.text(
                (x1 + 12, y1 + 34), "Nessuna notizia disponibile.", font=self.fonts.body, fill=INK_ON
            )
            return

        ny = y1 + 31
        for headline in news[:3]:
            draw_r.rectangle([x1 + 12, ny + 5, x1 + 17, ny + 10], fill=INK_ON)
            avail_w = x2 - (x1 + 25) - 10
            trunc = self._truncate(draw_b, str(headline), self.fonts.body, avail_w)
            draw_b.text((x1 + 25, ny), trunc, font=self.fonts.body, fill=INK_ON)
            ny += 24

    # ------------------------------------------------------------------
    # Section 8: Dynamic Widget - Grocery List
    # ------------------------------------------------------------------
    def _draw_grocery_list(
        self,
        draw_b: ImageDraw.ImageDraw,
        draw_r: ImageDraw.ImageDraw,
        grocery: List[Any],
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> None:
        if y2 < self.height:
            draw_b.line([(x1, y2), (x2, y2)], fill=INK_ON, width=2)

        draw_b.text((x1 + 12, y1 + 7), "LISTA DELLA SPESA", font=self.fonts.subhead, fill=INK_ON)
        count_str = f"{len(grocery)} ART."
        cw = self._text_width(draw_r, count_str, self.fonts.tiny) + 12
        self._draw_pill(
            draw_r,
            (x2 - cw - 12, y1 + 6, x2 - 12, y1 + 24),
            count_str,
            self.fonts.tiny,
            filled=False,
            radius=3,
        )

        if not grocery:
            draw_b.text(
                (x1 + 12, y1 + 36), "Lista vuota!", font=self.fonts.body, fill=INK_ON
            )
            return

        # 2-column checklist, up to 6 items
        col_w = (x2 - x1 - 24) // 2
        start_y = y1 + 32
        row_h = 24

        for idx, item in enumerate(grocery[:6]):
            col = idx % 2
            row = idx // 2
            ix = x1 + 12 + col * (col_w + 6)
            iy = start_y + row * row_h

            if isinstance(item, dict):
                label = str(item.get("name", ""))
                urgent = bool(item.get("urgent", False))
            else:
                label = str(item)
                urgent = False

            box_draw = draw_r if urgent else draw_b
            box_draw.rectangle([ix, iy + 3, ix + 10, iy + 13], outline=INK_ON, width=2)
            avail_w = col_w - 18
            trunc = self._truncate(draw_b, label, self.fonts.body, avail_w)
            draw_b.text((ix + 16, iy + 1), trunc, font=self.fonts.body, fill=INK_ON)


def render_dashboard(
    data: Dict[str, Any],
    preview_path: Optional[str] = "data/preview.png",
    now: Optional[datetime] = None,
) -> Tuple[Image.Image, Image.Image]:
    """Convenience wrapper around EPaperRenderer.render()."""
    renderer = EPaperRenderer()
    return renderer.render(data, now=now, preview_path=preview_path)


def get_sample_data(today: Optional[date] = None) -> Dict[str, Any]:
    """Sample payload for standalone testing and visual verification."""
    d0 = today or date.today()
    monday = d0 - timedelta(days=d0.weekday())

    calendar_days = [
        {
            "date": (monday + timedelta(days=0)).isoformat(),
            "events": [
                {"time": "09:00", "title": "Standup Ingegneria"},
                {"time": "17:30", "title": "Dentista Dott. Rossi"},
            ],
        },
        {
            "date": (monday + timedelta(days=1)).isoformat(),
            "events": [
                {"time": "08:30", "title": "Riunione Trimestrale", "important": True},
                {"time": "13:00", "title": "Pranzo con Marco"},
                {"time": "18:30", "title": "Colloquio Scuola"},
            ],
        },
        {
            "date": (monday + timedelta(days=2)).isoformat(),
            "events": [
                {"time": "10:00", "title": "Design Review E-Paper"},
            ],
        },
        {
            "date": (monday + timedelta(days=3)).isoformat(),
            "events": [
                {"time": "", "title": "Scadenza bolletta luce"},
                {"time": "15:00", "title": "Sync Fornitori"},
            ],
        },
        {
            "date": (monday + timedelta(days=4)).isoformat(),
            "events": [
                {"time": "11:00", "title": "Demo Prodotto"},
                {"time": "20:30", "title": "Cena dai nonni"},
            ],
        },
        {
            "date": (monday + timedelta(days=5)).isoformat(),
            "events": [
                {"time": "10:00", "title": "Partita Basket Under 12"},
            ],
        },
        {
            "date": (monday + timedelta(days=6)).isoformat(),
            "events": [],
        },
    ]

    return {
        "last_sync": "07:30",
        "battery_pct": 86,
        "calendar_days": calendar_days,
        "fixed_activities": [
            {"days": "LUN/MER", "time": "18:00", "title": "Nuoto"},
            {"days": "MAR", "time": "17:00", "title": "Chitarra"},
            {"days": "GIO", "time": "19:30", "title": "Calcetto"},
            {"days": "SAB", "time": "09:30", "title": "Mercato Rionale"},
        ],
        "mensa": {
            "today": {
                "primo": "Pasta al pomodoro e basilico",
                "secondo": "Polpette al forno",
                "contorno": "Carote e zucchine al vapore",
                "frutta": "Mela biologica",
            },
            "tomorrow": {
                "primo": "Risotto alla zucca",
                "secondo": "Filetto di platessa gratinato",
                "contorno": "Insalata mista di stagione",
                "frutta": "Pera Williams",
            },
        },
        "weather": {
            "city": "Milano",
            "temp": 13,
            "temp_min": 7,
            "temp_max": 16,
            "condition": "Parz. nuvoloso",
            "icon": "partly_cloudy",
        },
        "commute": {
            "duration_min": 24,
            "traffic_status": "REGOLARE",
            "route": "Tangenziale Est",
            "eta_note": "Arrivo stimato 08:54",
        },
        "news": [
            "Approvato il nuovo piano per la mobilità urbana",
            "Energia rinnovabile: record di produzione nel Q3",
            "Mostra sul design italiano aperta fino a gennaio",
        ],
        "grocery": [
            {"name": "Latte fresco", "urgent": True},
            "Pane integrale",
            "Uova bio (6)",
            "Pomodorini",
            {"name": "Caffè macinato", "urgent": True},
            "Mele Fuji",
        ],
    }


if __name__ == "__main__":
    sample = get_sample_data()
    for phase_name, test_hour in [("mattina", 8), ("pomeriggio", 15), ("sera", 20)]:
        test_dt = datetime.now().replace(hour=test_hour, minute=30, second=0, microsecond=0)
        b_img, r_img = render_dashboard(
            sample,
            preview_path=f"data/preview_{phase_name}.png",
            now=test_dt,
        )
        assert b_img.mode == "1" and b_img.size == (800, 480)
        assert r_img.mode == "1" and r_img.size == (800, 480)

    # Also write default data/preview.png
    render_dashboard(sample, preview_path="data/preview.png")
    print("Rendered 800x480 e-paper previews successfully.")
