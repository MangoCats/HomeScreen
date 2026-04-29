#!/usr/bin/env python3
"""HTTP server that serves a freshly rendered dashboard image on every request."""

import logging
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer

import dashboard

HOST = "0.0.0.0"
PORT = 2001

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # suppress default per-request noise
        pass

    def do_GET(self):
        if self.path not in ("/", "/dashboard.png"):
            self.send_response(404)
            self.end_headers()
            return

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


if __name__ == "__main__":
    log.info("Dashboard server on http://%s:%d/dashboard.png", HOST, PORT)
    HTTPServer((HOST, PORT), DashboardHandler).serve_forever()
