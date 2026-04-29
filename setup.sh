#!/usr/bin/env bash
# Sets up HomeScreen as a systemd service that starts on boot and restarts on failure.
# Idempotent — safe to run again after a git pull to apply updates.
# Run from the root of the cloned repository:  bash setup.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE="homescreen"
UNIT="/etc/systemd/system/${SERVICE}.service"

# ── Sanity check ─────────────────────────────────────────────────────────────

if [[ ! -f "$REPO_DIR/server.py" ]]; then
    echo "ERROR: run setup.sh from the root of the HomeScreen repository." >&2
    exit 1
fi

# ── Python virtual environment ────────────────────────────────────────────────

echo "==> Creating/updating virtual environment..."
python3 -m venv "$REPO_DIR/.venv"
"$REPO_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$REPO_DIR/.venv/bin/pip" install --quiet -r "$REPO_DIR/requirements.txt"

# ── systemd unit ──────────────────────────────────────────────────────────────

echo "==> Writing ${UNIT}..."
sudo tee "$UNIT" > /dev/null <<EOF
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

# ── Enable and (re)start ──────────────────────────────────────────────────────

echo "==> Enabling and restarting ${SERVICE}..."
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE"
sudo systemctl restart "$SERVICE"

echo ""
echo "Done."
echo "  Status : systemctl status ${SERVICE}"
echo "  Logs   : journalctl -u ${SERVICE} -f"
echo "  Image  : http://$(hostname -I | awk '{print $1}'):$(grep '^PORT' "$REPO_DIR/server.py" | awk -F= '{gsub(/ /,"",$2); print $2}')/dashboard.png"
