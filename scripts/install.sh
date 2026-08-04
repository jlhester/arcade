#!/usr/bin/env bash
# Installs the arcade systemd service for the current user.
set -euo pipefail

ARCADE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ARCADE_USER="${ARCADE_USER:-$(whoami)}"
SERVICE_NAME="arcade"
SERVICE_DEST="/etc/systemd/system/${SERVICE_NAME}.service"

echo "Installing arcade service from $ARCADE_DIR"
echo "Running as user: $ARCADE_USER"

# Create .env from example if missing
if [ ! -f "$ARCADE_DIR/.env" ]; then
    cp "$ARCADE_DIR/.env.example" "$ARCADE_DIR/.env"
    echo ""
    echo "Created .env from .env.example"
    echo "  → Edit $ARCADE_DIR/.env before starting the service"
fi

# Make scripts executable
chmod +x "$ARCADE_DIR/scripts/run.sh" "$ARCADE_DIR/scripts/arcade-mode.sh"

# Render both unit files: the button controller and the per-mode template.
render_unit() {
    local src="$1" dest="$2"
    sed \
        -e "s|__ARCADE_DIR__|$ARCADE_DIR|g" \
        -e "s|__ARCADE_USER__|$ARCADE_USER|g" \
        "$src" \
        | sudo tee "$dest" > /dev/null
}

render_unit "$ARCADE_DIR/systemd/arcade.service"  "$SERVICE_DEST"
render_unit "$ARCADE_DIR/systemd/arcade@.service" "/etc/systemd/system/arcade@.service"

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME.service"
sudo systemctl restart "$SERVICE_NAME.service"

echo ""
echo "Done. The button controller is running. Check status with:"
echo "  sudo systemctl status $SERVICE_NAME"
echo "  journalctl -u $SERVICE_NAME -f"
echo ""
echo "Force a single mode via systemd (stops the button controller):"
echo "  sudo systemctl start arcade@game        # or wallart / christmas / butterfly"
echo "  sudo $ARCADE_DIR/scripts/arcade-mode.sh wallart   # switch between forced modes"
echo "  sudo systemctl start arcade             # back to button control"
