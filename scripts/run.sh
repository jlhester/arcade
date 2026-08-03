#!/usr/bin/env bash
# Activates the blinka venv and launches the arcade.
#
#   run.sh            → the button-driven mode controller (arcade.service)
#   run.sh <mode>     → a single mode, directly (arcade@<mode>.service)
set -euo pipefail

ARCADE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${ARCADE_VENV:-$HOME/.venvs/blinka_venv}"

source "$VENV/bin/activate"

if [ "$#" -gt 0 ]; then
    exec python "$ARCADE_DIR/controller.py" --run-mode "$1"
else
    exec python "$ARCADE_DIR/controller.py"
fi
