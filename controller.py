#!/usr/bin/env python3
"""
Arcade LED panel mode controller.

Starts in the default mode and switches between modes when physical buttons
are pressed. Each mode runs as a managed subprocess; if it crashes, the
controller restarts it automatically.

Modes and button-to-mode mapping are configured via environment variables.
See .env.example for all options.
"""
import argparse
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).parent

# ── Config from environment ────────────────────────────────────────────────
LOG_DIR = os.environ.get("ARCADE_LOG_DIR", "/home/arcadeuser/logs")
PICO8_BIN = os.environ.get("ARCADE_PICO8_BIN", "/home/arcadeuser/pico-8/pico8_64")
BRIGHTNESS = os.environ.get("ARCADE_BRIGHTNESS", "0.5")
LOOP_LENGTH = os.environ.get("ARCADE_LOOP_LENGTH", "60")
FRAME_DELAY = os.environ.get("ARCADE_FRAME_DELAY", "0.2")
DEFAULT_MODE = os.environ.get("ARCADE_DEFAULT_MODE", "wallart")

# GIF directories — one per named art category
_WALLART_BASE = os.environ.get("ARCADE_HOME", "/home/arcadeuser") + "/wallart"
GIF_DIRS: dict[str, str] = {
    "wallart":     os.environ.get("ARCADE_GIF_DIR_WALLART",     f"{_WALLART_BASE}/wallart-gifs"),
    "christmas":   os.environ.get("ARCADE_GIF_DIR_CHRISTMAS",   f"{_WALLART_BASE}/xmas-gifs"),
    "butterflies": os.environ.get("ARCADE_GIF_DIR_BUTTERFLIES", f"{_WALLART_BASE}/butterfly-gifs"),
    "halloween":   os.environ.get("ARCADE_GIF_DIR_HALLOWEEN",   f"{_WALLART_BASE}/halloween-gifs"),
    # add more categories here
}

# A single GIF looped forever (butterfly mode)
BUTTERFLY_GIF = os.environ.get("ARCADE_BUTTERFLY_GIF", f"{_WALLART_BASE}/butterfly-gifs/butterfly.gif")

# GPIO BCM pin numbers for each mode button (0 = disabled)
BTN_WALLART_PIN     = int(os.environ.get("ARCADE_BTN_WALLART_PIN",     "17"))
BTN_GAME_PIN        = int(os.environ.get("ARCADE_BTN_GAME_PIN",        "27"))
BTN_CHRISTMAS_PIN   = int(os.environ.get("ARCADE_BTN_CHRISTMAS_PIN",   "0"))
BTN_BUTTERFLIES_PIN = int(os.environ.get("ARCADE_BTN_BUTTERFLIES_PIN", "0"))
BTN_BUTTERFLY_PIN   = int(os.environ.get("ARCADE_BTN_BUTTERFLY_PIN",   "0"))
BTN_HALLOWEEN_PIN   = int(os.environ.get("ARCADE_BTN_HALLOWEEN_PIN",   "0"))

PYTHON = sys.executable
_ART = str(HERE / "modes" / "art.py")

# ── Mode definitions ────────────────────────────────────────────────────────
# Each mode is a command list passed to subprocess.Popen.
# GIF category modes all use the same art.py script with a different --dir.
MODES: dict[str, list[str]] = {
    "wallart": [
        PYTHON, _ART, "--dir", GIF_DIRS["wallart"],
    ],
    "christmas": [
        PYTHON, _ART, "--dir", GIF_DIRS["christmas"],
    ],
    "butterflies": [
        PYTHON, _ART, "--dir", GIF_DIRS["butterflies"],
    ],
    "butterfly": [
        PYTHON, _ART, "--file", BUTTERFLY_GIF,
    ],
    "halloween": [
        PYTHON, _ART, "--dir", GIF_DIRS["halloween"],
    ],
    "game": [
        PYTHON, str(HERE / "virtualdisplay.py"),
        "--brightness", BRIGHTNESS,
        "--pinout", "AdafruitMatrixBonnet",
        "--backend", "xvfb",
        "--width", "128",
        "--height", "128",
        "--serpentine",
        "--num-address-lines", "5",
        "--num-planes", "6",
        "--", PICO8_BIN, "-splore",
    ],
}

# Map GPIO pin → mode name. Zero-valued pins are skipped.
BUTTON_MAP: dict[int, str] = {
    pin: mode
    for pin, mode in [
        (BTN_WALLART_PIN,     "wallart"),
        (BTN_GAME_PIN,        "game"),
        (BTN_CHRISTMAS_PIN,   "christmas"),
        (BTN_BUTTERFLIES_PIN, "butterflies"),
        (BTN_BUTTERFLY_PIN,   "butterfly"),
        (BTN_HALLOWEEN_PIN,   "halloween"),
    ]
    if pin
}

# ── Logging ─────────────────────────────────────────────────────────────────
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "controller.log")),
        logging.StreamHandler(),
    ],
    level=logging.INFO,
)
logger = logging.getLogger("controller")


def _mode_env() -> dict:
    """Environment passed to every mode subprocess."""
    env = os.environ.copy()
    env.update({
        "ARCADE_LOG_DIR": LOG_DIR,
        "ARCADE_BRIGHTNESS": BRIGHTNESS,
        "ARCADE_LOOP_LENGTH": LOOP_LENGTH,
        "ARCADE_FRAME_DELAY": FRAME_DELAY,
    })
    return env


def run_single_mode(mode: str) -> None:
    """Replace this process with a single mode's command.

    Used by the systemd template unit (arcade@<mode>.service) to run one mode
    directly — no GPIO, no restart loop. systemd owns the resulting process and
    delivers signals to it, so exec (rather than a managed subprocess) is what
    we want here.
    """
    if mode not in MODES:
        logger.error("Unknown mode: %s", mode)
        sys.exit(2)
    logger.info("Running %s mode directly (systemd)", mode)
    cmd = MODES[mode]
    os.execvpe(cmd[0], cmd, _mode_env())


class ModeController:
    def __init__(self) -> None:
        self.current_mode: str | None = None
        self.current_proc: subprocess.Popen | None = None
        self._lock = threading.Lock()

    def switch_to(self, mode: str) -> None:
        with self._lock:
            if mode == self.current_mode:
                logger.info("Already in %s mode, ignoring button press", mode)
                return
            if mode not in MODES:
                logger.error("Unknown mode: %s", mode)
                return
            self._stop_current()
            logger.info("Starting %s mode", mode)
            self.current_proc = subprocess.Popen(MODES[mode], env=_mode_env())
            self.current_mode = mode

    def restart_current(self) -> None:
        """Restart a crashed mode without switching."""
        with self._lock:
            mode = self.current_mode
            if mode is None:
                return
            logger.warning("%s mode exited unexpectedly, restarting", mode)
            self.current_mode = None
        self.switch_to(mode)

    def _stop_current(self) -> None:
        if self.current_proc and self.current_proc.poll() is None:
            logger.info("Stopping %s mode", self.current_mode)
            self.current_proc.terminate()
            try:
                self.current_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Mode did not stop cleanly, killing")
                self.current_proc.kill()
        self.current_proc = None

    def is_running(self) -> bool:
        return self.current_proc is not None and self.current_proc.poll() is None

    def shutdown(self) -> None:
        with self._lock:
            self._stop_current()
            self.current_mode = None


def _setup_gpio(controller: ModeController) -> None:
    """Wire GPIO buttons to mode switches. Silently skips if GPIO unavailable."""
    if not BUTTON_MAP:
        logger.info("No GPIO buttons configured")
        return

    # Pi 5 requires lgpio as the pin factory
    os.environ.setdefault("GPIOZERO_PIN_FACTORY", "lgpio")

    try:
        from gpiozero import Button

        for pin, mode in BUTTON_MAP.items():
            btn = Button(pin, pull_up=True, bounce_time=0.1)
            btn.when_pressed = lambda m=mode: controller.switch_to(m)
            logger.info("Button on GPIO %d → %s mode", pin, mode)
    except Exception:
        logger.warning("GPIO unavailable — physical buttons disabled", exc_info=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Arcade LED panel mode controller")
    parser.add_argument(
        "--run-mode",
        metavar="MODE",
        help="Run a single mode directly and exit (used by the arcade@ systemd unit). "
             "Bypasses GPIO buttons and the restart loop.",
    )
    args = parser.parse_args()

    if args.run_mode:
        run_single_mode(args.run_mode)
        return  # unreachable: run_single_mode execs

    controller = ModeController()

    def handle_signal(sig, frame):
        logger.info("Received signal %s, shutting down", sig)
        controller.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    _setup_gpio(controller)
    controller.switch_to(DEFAULT_MODE)

    while True:
        if not controller.is_running():
            controller.restart_current()
        time.sleep(5)


if __name__ == "__main__":
    main()
