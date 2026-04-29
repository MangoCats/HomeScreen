HomeScreen
==========
A dashboard image server for the Google Nest Hub (or any screen that can
display a URL).  It renders a 1024x600 PNG on demand and serves it over HTTP.
The image is regenerated on every request so the clock and any live data are
always current.


What it displays
----------------
  Moon phase   Right side of the screen, 80 % of screen height, vertically
               centered.  Fetched as a 1000x1000 PNG from a local Home
               Assistant instance and scaled to fit.

  Clock        Current time (12-hour, no leading zero, e.g. "3:45") in bold
               sans-serif at 20 % of screen height, left-justified at the
               bottom of the frame.


How it works
------------
server.py     Tiny Python HTTP server.  On every GET /, GET /dashboard.png
              request it builds the image in memory and returns it with
              Cache-Control: no-store so clients always get a fresh render.

dashboard.py  Image composition module.  Imports Pillow to draw onto a black
              canvas, then calls each module's render_* function in order.
              Can also be run directly to write a one-shot PNG to disk:

                python3 dashboard.py [output.png]

              New display modules (weather, calendar, etc.) are added here as
              render_* functions and wired into generate().


Files
-----
  dashboard.py      Image generation and all render modules
  server.py         HTTP server (default port 2001)
  setup.sh          Raspberry Pi setup — installs deps, creates systemd service
  requirements.txt  Python dependencies (Pillow, requests)
  .gitignore        Excludes .venv/ and generated dashboard.png


Dependencies
------------
  Python 3.8+
  Pillow  (image compositing)
  requests  (fetches moon image over HTTP)

A bold sans-serif TrueType font must be present on the system.  The following
paths are tried in order; the first one found is used:

  /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf       (Raspberry Pi OS default)
  /usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf
  /usr/share/fonts/truetype/noto/NotoSans-Bold.ttf
  /usr/share/fonts/truetype/freefont/FreeSansBold.ttf


Raspberry Pi setup
------------------
Clone the repository and run setup.sh once:

  git clone <repo-url> ~/HomeScreen
  cd ~/HomeScreen
  bash setup.sh

setup.sh will:
  1. Create a Python virtual environment at .venv/
  2. Install Python dependencies into it
  3. Write a systemd unit file to /etc/systemd/system/homescreen.service
  4. Enable the service (starts automatically on every boot)
  5. Start the service immediately

The script is idempotent — run it again after any git pull to apply changes:

  git pull
  bash setup.sh

Useful commands:
  systemctl status homescreen          check running state
  journalctl -u homescreen -f          tail live logs
  sudo systemctl stop homescreen       stop the server
  sudo systemctl disable homescreen    prevent start on boot


Configuration
-------------
All tuneable values are constants at the top of dashboard.py:

  SCREEN_W / SCREEN_H      Output image dimensions in pixels (default 1024x600)
  BACKGROUND               RGB background colour (default black: 0, 0, 0)

  MOON_URL                 URL of the moon phase image
                           (default http://homeassistant:1969/moon.png)
  MOON_HEIGHT_RATIO        Moon diameter as a fraction of SCREEN_H (default 0.80)
  MOON_MARGIN_RIGHT        Pixels between moon and right edge (default 0)

  CLOCK_COLOR              RGB colour of clock text (default white: 255, 255, 255)
  CLOCK_FONT_RATIO         Font size as a fraction of SCREEN_H (default 0.20)
  CLOCK_MARGIN_LEFT        Pixels from left edge (default 24)
  CLOCK_MARGIN_BOTTOM      Pixels above bottom edge (default 16)

  FONT_CANDIDATES          Ordered list of font file paths to try

The server port is set in server.py:

  PORT = 2001

After changing any value, restart the service:

  sudo systemctl restart homescreen


Displaying on a Google Nest Hub
--------------------------------
The Nest Hub is a Chromecast device.  Cast the dashboard URL to it using
pychromecast:

  pip install pychromecast
  python3 - <<'EOF'
  import pychromecast
  cast, browser = pychromecast.find_chromecasts(friendly_name="Your Hub Name")
  cast.wait()
  cast.media_controller.play_media("http://<pi-ip>:2001/dashboard.png", "image/png")
  EOF

Or trigger it from Home Assistant via the Cast integration:

  service: media_player.play_media
  target:
    entity_id: media_player.your_hub
  data:
    media_content_id: http://<pi-ip>:2001/dashboard.png
    media_content_type: image/png

Because the Nest Hub will eventually return to ambient mode, re-cast
periodically (every 60 seconds matches the clock refresh granularity).


Adding new display modules
--------------------------
1. Write a render_*(canvas) function in dashboard.py that draws onto the
   Pillow Image passed to it.
2. Call it from generate() in the order you want layers composited.
3. Add any new dependencies to requirements.txt and re-run setup.sh.
