#!/usr/bin/env bash
# Activates the blinka venv and launches the mode controller.
set -euo pipefail

ARCADE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${ARCADE_VENV:-$HOME/.venvs/blinka_venv}"

source "$VENV/bin/activate"
exec python "$ARCADE_DIR/controller.py"
