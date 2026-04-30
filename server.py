#!/usr/bin/env python3
"""HTTP server that serves a freshly rendered dashboard image on every request."""

import io
import logging
import threading
import time
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from PIL import Image

import dashboard

HOST = "0.0.0.0"
PORT = 2001
MJPEG_BOUNDARY = "frame"
MJPEG_HZ = 2  # push cadence; max display lag = 1/MJPEG_HZ seconds

# Served as-is; the browser on the Cast device handles MJPEG natively in <img>.
_HTML = (
    b"<!DOCTYPE html><html><head>"
    b"<style>*{margin:0;padding:0}body{background:#000;overflow:hidden}"
    b"img{display:block;width:100vw;height:100vh;object-fit:contain}</style>"
    b"</head><body>"
    b'<img src="/dashboard.mjpeg">'
    b"</body></html>"
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Shared frame cache (written by _refresh_loop, read by every MJPEG client) ─

_frame_lock = threading.Lock()
_cached_frame: bytes = b""


def _to_jpeg(png_bytes: bytes) -> bytes:
    buf = io.BytesIO()
    Image.open(io.BytesIO(png_bytes)).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _sleep_until_next_minute(offset: float = 2.0) -> None:
    """Sleep until `offset` seconds past the next local minute boundary.

    Polls the clock in the final seconds rather than relying on sleep accuracy,
    so the frame is never generated before the minute has actually rolled over.
    """
    now = datetime.now()
    current_minute = now.minute
    bulk = 60 - now.second - now.microsecond / 1_000_000 - 2
    if bulk > 0:
        time.sleep(bulk)
    while datetime.now().minute == current_minute:
        time.sleep(0.05)
    time.sleep(offset)


def _refresh_loop() -> None:
    """Background thread: regenerate the dashboard JPEG once per minute."""
    global _cached_frame
    while True:
        try:
            log.info("Rendering at %s", datetime.now().strftime("%H:%M:%S.%f"))
            frame = _to_jpeg(dashboard.generate())
            with _frame_lock:
                _cached_frame = frame
            log.info("Frame updated (%d bytes)", len(frame))
        except Exception:
            log.error("Frame render failed:\n%s", traceback.format_exc())
            time.sleep(5)
            continue
        _sleep_until_next_minute()


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # suppress default per-request noise
        pass

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/dashboard.mjpeg":
            self._serve_mjpeg()
        elif path == "/dashboard.html":
            self._serve_html()
        elif path in ("/", "/dashboard.png"):
            self._serve_png()
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_html(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(_HTML)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(_HTML)
        log.info("Served dashboard.html")

    def _serve_png(self):
        try:
            image_bytes = dashboard.generate()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(image_bytes)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(image_bytes)
            log.info("Served dashboard.png (%d bytes)", len(image_bytes))
        except Exception:
            log.error("Render failed:\n%s", traceback.format_exc())
            self.send_response(500)
            self.end_headers()

    def _serve_mjpeg(self):
        self.send_response(200)
        self.send_header("Content-Type", f"multipart/x-mixed-replace;boundary={MJPEG_BOUNDARY}")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        log.info("MJPEG stream started")
        try:
            while True:
                with _frame_lock:
                    frame = _cached_frame
                if frame:
                    self._push_mjpeg_frame(frame)
                    time.sleep(1.0 / MJPEG_HZ)
                else:
                    time.sleep(0.1)  # spin until first frame is ready
        except Exception:
            log.info("MJPEG stream ended")

    def _push_mjpeg_frame(self, jpeg_bytes: bytes) -> None:
        self.wfile.write(
            f"--{MJPEG_BOUNDARY}\r\nContent-Type: image/jpeg\r\n"
            f"Content-Length: {len(jpeg_bytes)}\r\n\r\n".encode()
            + jpeg_bytes + b"\r\n"
        )
        self.wfile.flush()


if __name__ == "__main__":
    threading.Thread(target=_refresh_loop, daemon=True).start()
    log.info("Dashboard server on http://%s:%d/", HOST, PORT)
    ThreadingHTTPServer((HOST, PORT), DashboardHandler).serve_forever()
