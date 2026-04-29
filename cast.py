#!/usr/bin/env python3
"""Periodically casts the dashboard image to a Google Cast device."""

import logging
import os
import time

import pychromecast

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DEVICE_NAME   = os.environ["CAST_DEVICE"]
DASHBOARD_URL = os.environ["DASHBOARD_URL"]
INTERVAL      = int(os.environ.get("CAST_INTERVAL", "55"))


def cast_once() -> None:
    chromecasts, browser = pychromecast.get_listed_chromecasts(
        friendly_names=[DEVICE_NAME]
    )
    try:
        if not chromecasts:
            log.warning("Device '%s' not found on network", DEVICE_NAME)
            return
        cast = chromecasts[0]
        cast.wait(timeout=10)
        url = f"{DASHBOARD_URL}?t={int(time.time())}"
        cast.media_controller.play_media(url, "image/png")
        log.info("Cast → %s", url)
    finally:
        browser.stop_discovery()


if __name__ == "__main__":
    while True:
        try:
            cast_once()
        except Exception as exc:
            log.error("Cast failed: %s", exc)
        time.sleep(INTERVAL)
