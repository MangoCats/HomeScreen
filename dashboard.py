#!/usr/bin/env python3
"""Dashboard image generator for Google Home screen display."""

import io
import logging
import sys
from datetime import datetime
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

SCREEN_W = 1024
SCREEN_H = 600
BACKGROUND = (0, 0, 0)

MOON_URL = "http://homeassistant:1969/moon.png"
BAL_URL  = "http://homeassistant:8765/account.json"

CLOCK_COLOR = (255, 255, 255)
CLOCK_FONT_RATIO = 0.20   # font size as fraction of screen height
CLOCK_MARGIN_LEFT = 24
DATE_FONT_SIZE = 38

MOON_HEIGHT_RATIO = 0.80  # moon diameter as fraction of screen height

# Font candidates — bold and regular (first match wins)
FONT_CANDIDATES_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]
FONT_CANDIDATES_REGULAR = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
]

# ── Helpers ──────────────────────────────────────────────────────────────────

def load_font(size: int, bold: bool = True) -> ImageFont.ImageFont:
    for path in (FONT_CANDIDATES_BOLD if bold else FONT_CANDIDATES_REGULAR):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def fetch_moon() -> Image.Image:
    resp = requests.get(MOON_URL, timeout=10)
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("RGBA")


def fetch_balance() -> list[str]:
    """Return lines to display: balance then transactions, or error message."""
    try:
        resp = requests.get(BAL_URL, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            return ["Balance not available"]
        bal = data["balance"]["available"]
        lines = [f"${bal:,.2f}"]
        for tx in data.get("transactions", []):
            lines.append(f"{tx['date']}  {tx['amount']:,.2f}  {tx['description']}")
        return lines
    except Exception as exc:
        log.warning("Balance fetch failed: %s", exc)
        return ["Balance not available"]

# ── Modules ──────────────────────────────────────────────────────────────────

def render_moon(canvas: Image.Image) -> None:
    """Right side; equal margin on top, bottom, and right."""
    try:
        moon_img = fetch_moon()
    except Exception as exc:
        log.warning("Moon fetch failed, skipping: %s", exc)
        return
    moon_px = int(SCREEN_H * MOON_HEIGHT_RATIO)
    moon_img = moon_img.resize((moon_px, moon_px), Image.LANCZOS)
    margin = (SCREEN_H - moon_px) // 2
    x = SCREEN_W - moon_px - margin
    y = margin
    canvas.paste(moon_img, (x, y), moon_img)


def render_clock_and_date(canvas: Image.Image) -> int:
    """Clock (bold, 20% height) above date line (regular, 38 px), both left-justified.
    Returns clock_y so render_balance can stop one line above it."""
    draw = ImageDraw.Draw(canvas)
    moon_px = int(SCREEN_H * MOON_HEIGHT_RATIO)
    margin_bottom = (SCREEN_H - moon_px) // 4  # half the moon's bottom gap
    bottom = SCREEN_H - margin_bottom           # y-coordinate of the shared baseline

    # Date line — sits at the bottom
    date_font = load_font(DATE_FONT_SIZE, bold=False)
    date_str = datetime.now().strftime("%A %B %-d")
    date_bbox = draw.textbbox((0, 0), date_str, font=date_font)
    date_h = date_bbox[3] - date_bbox[1]
    date_y = bottom - date_h

    # Clock — sits above the date line with one date-font line-gap of spacing
    clock_font_px = int(SCREEN_H * CLOCK_FONT_RATIO)
    clock_font = load_font(clock_font_px, bold=True)
    time_str = datetime.now().strftime("%-I:%M")
    clock_bbox = draw.textbbox((0, 0), time_str, font=clock_font)
    clock_h = clock_bbox[3] - clock_bbox[1]
    gap = DATE_FONT_SIZE // 5 + 16  # ~8 px leading + 16 px additional offset
    clock_y = date_y - gap - clock_h

    draw.text((CLOCK_MARGIN_LEFT, clock_y), time_str, font=clock_font, fill=CLOCK_COLOR)
    draw.text((CLOCK_MARGIN_LEFT, date_y), date_str, font=date_font, fill=CLOCK_COLOR)
    return clock_y


def render_balance(canvas: Image.Image, clock_y: int) -> None:
    """Balance and transactions, top-left; same font/margins as date display."""
    draw = ImageDraw.Draw(canvas)
    bal_font = load_font(DATE_FONT_SIZE, bold=False)
    tx_font  = load_font(DATE_FONT_SIZE // 2, bold=False)

    moon_px = int(SCREEN_H * MOON_HEIGHT_RATIO)
    top_margin = (SCREEN_H - moon_px) // 4  # mirrors the bottom margin used by date/clock

    def line_metrics(font):
        bb = draw.textbbox((0, 0), "Ay", font=font)
        h = bb[3] - bb[1]
        return h, h + h // 5

    bal_h,  bal_stride = line_metrics(bal_font)
    tx_h,   tx_stride  = line_metrics(tx_font)

    lines = fetch_balance()
    y = top_margin
    for i, line in enumerate(lines):
        font   = bal_font if i == 0 else tx_font
        lh, ls = (bal_h, bal_stride) if i == 0 else (tx_h, tx_stride)
        if y + lh + ls > clock_y:
            break
        draw.text((CLOCK_MARGIN_LEFT, y), line, font=font, fill=CLOCK_COLOR)
        y += ls

# ── Entry point ──────────────────────────────────────────────────────────────

def generate() -> bytes:
    canvas = Image.new("RGB", (SCREEN_W, SCREEN_H), BACKGROUND)
    render_moon(canvas)
    clock_y = render_clock_and_date(canvas)
    render_balance(canvas, clock_y)
    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "dashboard.png"
    Path(out).write_bytes(generate())
    print(f"Saved → {out}")
