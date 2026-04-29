#!/usr/bin/env bash
# Sets up HomeScreen as two systemd services that start on boot and restart on failure.
#   homescreen       – image server
#   homescreen-cast  – periodic Chromecast controller
# Idempotent — safe to run again after a git pull to apply updates.
# Run from the root of the cloned repository:  bash setup.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$REPO_DIR/homescreen.env"

# ── Sanity check ──────────────────────────────────────────────────────────────

if [[ ! -f "$REPO_DIR/server.py" ]]; then
    echo "ERROR: run setup.sh from the root of the HomeScreen repository." >&2
    exit 1
fi

# ── Python virtual environment ────────────────────────────────────────────────

echo "==> Creating/updating virtual environment..."
python3 -m venv "$REPO_DIR/.venv"
"$REPO_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$REPO_DIR/.venv/bin/pip" install --quiet -r "$REPO_DIR/requirements.txt"

# ── Cast configuration ────────────────────────────────────────────────────────
# CAST_DEVICE is prompted once and preserved across re-runs.
# DASHBOARD_URL is recomputed each run in case the Pi's IP has changed.

PORT=$(grep '^PORT' "$REPO_DIR/server.py" | awk -F= '{gsub(/ /,"",$2); print $2}')
PI_IP=$(hostname -I | awk '{print $1}')
DASHBOARD_URL="http://${PI_IP}:${PORT}/dashboard.png"

# Preserve existing CAST_DEVICE if already configured
CAST_DEVICE=""
if [[ -f "$ENV_FILE" ]]; then
    CAST_DEVICE=$(grep '^CAST_DEVICE=' "$ENV_FILE" | cut -d= -f2- || true)
fi

if [[ -z "$CAST_DEVICE" ]]; then
    echo "==> Scanning for Cast devices on the network (5 s)..."
    "$REPO_DIR/.venv/bin/python3" <<'PYEOF'
import pychromecast
chromecasts, browser = pychromecast.get_chromecasts(timeout=5)
pychromecast.discovery.stop_discovery(browser)
names = sorted(cc.cast_info.friendly_name for cc in chromecasts)
if names:
    for name in names:
        print(f"    {name}")
else:
    print("    (no devices found — check that this machine is on the same network)")
PYEOF
    read -rp "Enter device name: " CAST_DEVICE
fi

echo "==> Writing ${ENV_FILE}..."
cat > "$ENV_FILE" <<EOF
CAST_DEVICE=${CAST_DEVICE}
DASHBOARD_URL=${DASHBOARD_URL}
CAST_INTERVAL=55
EOF

# ── systemd unit: image server ────────────────────────────────────────────────

echo "==> Writing /etc/systemd/system/homescreen.service..."
sudo tee /etc/systemd/system/homescreen.service > /dev/null <<EOF
[Unit]
Description=HomeScreen Dashboard Server
After=network.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${REPO_DIR}
ExecStart=${REPO_DIR}/.venv/bin/python3 ${REPO_DIR}/server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# ── systemd unit: cast controller ────────────────────────────────────────────

echo "==> Writing /etc/systemd/system/homescreen-cast.service..."
sudo tee /etc/systemd/system/homescreen-cast.service > /dev/null <<EOF
[Unit]
Description=HomeScreen Cast Controller
After=network.target homescreen.service
Wants=homescreen.service

[Service]
Type=simple
User=${USER}
WorkingDirectory=${REPO_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${REPO_DIR}/.venv/bin/python3 ${REPO_DIR}/cast.py
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# ── Enable and (re)start both services ───────────────────────────────────────

echo "==> Enabling and restarting services..."
sudo systemctl daemon-reload
sudo systemctl enable homescreen homescreen-cast
sudo systemctl restart homescreen homescreen-cast

echo ""
echo "Done."
echo "  Dashboard : ${DASHBOARD_URL}"
echo "  Cast to   : ${CAST_DEVICE}"
echo ""
echo "  Server logs : journalctl -u homescreen -f"
echo "  Cast logs   : journalctl -u homescreen-cast -f"
