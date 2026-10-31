#!/usr/bin/env bash
# Force a single arcade mode via systemd, ensuring nothing else owns the matrix.
#
# Stops the button controller and any other forced mode, then starts the one
# requested. Run with sudo (systemctl needs privileges).
#
#   sudo scripts/arcade-mode.sh game
#   sudo scripts/arcade-mode.sh wallart
#   sudo scripts/arcade-mode.sh christmas
#   sudo scripts/arcade-mode.sh butterfly
#
# To hand control back to the buttons:  sudo systemctl start arcade
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "usage: $0 <mode>   (game | wallart | christmas | butterflies | butterfly | halloween)" >&2
    exit 1
fi

MODE="$1"

# Stop every forced-mode instance first (glob), then start the requested one.
# arcade.service is stopped automatically by Conflicts= when arcade@ starts.
systemctl stop 'arcade@*.service' 2>/dev/null || true
systemctl start "arcade@${MODE}.service"

echo "Now running arcade@${MODE}. (buttons disabled until 'systemctl start arcade')"
