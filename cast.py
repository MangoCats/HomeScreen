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
            url = f"{DASHBOARD_URL}?t={int(time.time())}"
            cast.media_controller.play_media(url, "image/png")
            log.info("Cast → %s", url)
        except Exception as exc:
            log.error("Cast failed: %s", exc)
            cast = None
        time.sleep(INTERVAL)
