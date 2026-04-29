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

CLOCK_COLOR = (255, 255, 255)
CLOCK_FONT_RATIO = 0.20   # font size as fraction of screen height
CLOCK_MARGIN_LEFT = 24

MOON_HEIGHT_RATIO = 0.80  # moon diameter as fraction of screen height

# Bold sans-serif font candidates (first match wins)
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]

# ── Helpers ──────────────────────────────────────────────────────────────────

def load_font(size: int) -> ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def fetch_moon() -> Image.Image:
    resp = requests.get(MOON_URL, timeout=10)
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("RGBA")

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


def render_clock(canvas: Image.Image) -> None:
    """Bold sans-serif, 20 % of screen height, left-justified at the bottom."""
    font_px = int(SCREEN_H * CLOCK_FONT_RATIO)
    font = load_font(font_px)
    draw = ImageDraw.Draw(canvas)
    time_str = datetime.now().strftime("%-I:%M")
    bbox = draw.textbbox((0, 0), time_str, font=font)
    text_h = bbox[3] - bbox[1]
    moon_px = int(SCREEN_H * MOON_HEIGHT_RATIO)
    margin_bottom = (SCREEN_H - moon_px) // 4  # half the moon's bottom gap
    x = CLOCK_MARGIN_LEFT
    y = SCREEN_H - text_h - margin_bottom
    draw.text((x, y), time_str, font=font, fill=CLOCK_COLOR)

# ── Entry point ──────────────────────────────────────────────────────────────

def generate() -> bytes:
    canvas = Image.new("RGB", (SCREEN_W, SCREEN_H), BACKGROUND)
    render_moon(canvas)
    render_clock(canvas)
    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "dashboard.png"
    Path(out).write_bytes(generate())
    print(f"Saved → {out}")
