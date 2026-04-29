#!/usr/bin/env python3
"""Periodically casts the dashboard MJPEG stream to a Google Cast device."""

import logging
import os
import time
from urllib.parse import urlparse, urlunparse

import pychromecast
from pychromecast.controllers.media import STREAM_TYPE_LIVE

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DEVICE_NAME   = os.environ["CAST_DEVICE"]
DASHBOARD_URL = os.environ["DASHBOARD_URL"]
INTERVAL      = int(os.environ.get("CAST_INTERVAL", "55"))

# Derive MJPEG URL from the configured host:port regardless of path in DASHBOARD_URL
_parsed = urlparse(DASHBOARD_URL)
MJPEG_URL = urlunparse(_parsed._replace(path="/dashboard.mjpeg", query=""))


def connect() -> tuple[pychromecast.Chromecast, object]:
    chromecasts, browser = pychromecast.get_listed_chromecasts(
        friendly_names=[DEVICE_NAME]
    )
    if not chromecasts:
        browser.stop_discovery()
        raise RuntimeError(f"Device '{DEVICE_NAME}' not found on network")
    cast = chromecasts[0]
    cast.wait(timeout=10)
    log.info("Connected to '%s'", DEVICE_NAME)
    return cast, browser


if __name__ == "__main__":
    cast = None
    browser = None
    while True:
        try:
            if cast is None:
                if browser is not None:
                    browser.stop_discovery()
                cast, browser = connect()
            mc = cast.media_controller
            if mc.status.player_state not in ("PLAYING", "BUFFERING"):
                url = f"{MJPEG_URL}?t={int(time.time())}"
                mc.play_media(url, "image/jpeg", stream_type=STREAM_TYPE_LIVE)
                log.info("Cast → %s", url)
            else:
                log.info("MJPEG stream active")
        except Exception as exc:
            log.error("Cast failed: %s", exc)
            cast = None
        time.sleep(INTERVAL)
