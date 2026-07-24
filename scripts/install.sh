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
chmod +x "$ARCADE_DIR/scripts/run.sh"

# Render service template
sed \
    -e "s|__ARCADE_DIR__|$ARCADE_DIR|g" \
    -e "s|__ARCADE_USER__|$ARCADE_USER|g" \
    "$ARCADE_DIR/systemd/arcade.service" \
    | sudo tee "$SERVICE_DEST" > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME.service"
sudo systemctl restart "$SERVICE_NAME.service"

echo ""
echo "Done. Check status with:"
echo "  sudo systemctl status $SERVICE_NAME"
echo "  journalctl -u $SERVICE_NAME -f"
