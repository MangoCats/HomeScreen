#!/usr/bin/env python3
"""Casts the dashboard HTML page to a Google Cast device via DashCast."""

import logging
import os
import time
from urllib.parse import urlparse, urlunparse

import pychromecast
from pychromecast.controllers import BaseController

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DEVICE_NAME   = os.environ["CAST_DEVICE"]
DASHBOARD_URL = os.environ["DASHBOARD_URL"]
INTERVAL      = int(os.environ.get("CAST_INTERVAL", "55"))

# DashCast: a Cast receiver that opens a Chrome webview to any URL.
# The HTML page embeds the MJPEG stream; Chrome handles multipart/x-mixed-replace
# natively in <img>, so the display stays live without triggering the idle timeout.
DASHCAST_APP_ID   = "5C3F0A3C"
DASHCAST_NAMESPACE = "urn:x-cast:es.offd.dashcast"

# Derive the HTML page URL from the configured host:port
_parsed = urlparse(DASHBOARD_URL)
DASHBOARD_HTML_URL = urlunparse(_parsed._replace(path="/dashboard.html", query=""))


class DashCastController(BaseController):
    def __init__(self):
        super().__init__(DASHCAST_NAMESPACE, DASHCAST_APP_ID)

    def load_url(self, url: str) -> None:
        self.send_message({"url": url, "force": True})


def connect() -> tuple[pychromecast.Chromecast, object, DashCastController]:
    chromecasts, browser = pychromecast.get_listed_chromecasts(
        friendly_names=[DEVICE_NAME]
    )
    if not chromecasts:
        browser.stop_discovery()
        raise RuntimeError(f"Device '{DEVICE_NAME}' not found on network")
    cast = chromecasts[0]
    cast.wait(timeout=10)
    dashcast = DashCastController()
    cast.register_handler(dashcast)
    log.info("Connected to '%s'", DEVICE_NAME)
    return cast, browser, dashcast


if __name__ == "__main__":
    cast = None
    browser = None
    dashcast = None
    while True:
        try:
            if cast is None:
                if browser is not None:
                    browser.stop_discovery()
                cast, browser, dashcast = connect()
            if cast.app_id != DASHCAST_APP_ID:
                cast.start_app(DASHCAST_APP_ID)
                time.sleep(2)  # wait for receiver to initialise
                dashcast.load_url(DASHBOARD_HTML_URL)
                log.info("Cast → %s", DASHBOARD_HTML_URL)
            else:
                log.info("DashCast session active")
        except Exception as exc:
            log.error("Cast failed: %s", exc)
            cast = None
        time.sleep(INTERVAL)
