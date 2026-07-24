#!/usr/bin/env python3
"""
Arcade LED panel mode controller.

Starts in the default mode and switches between modes when physical buttons
are pressed. Each mode runs as a managed subprocess; if it crashes, the
controller restarts it automatically.

Modes and button-to-mode mapping are configured via environment variables.
See .env.example for all options.
"""
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
DEFAULT_MODE = os.environ.get("ARCADE_DEFAULT_MODE", "art")

# GIF directories — one per named art category
_WALLART_BASE = os.environ.get("ARCADE_HOME", "/home/arcadeuser") + "/wallart"
GIF_DIRS: dict[str, str] = {
    "art":         os.environ.get("ARCADE_GIF_DIR",             f"{_WALLART_BASE}/wallart-gifs"),
    "xmas":        os.environ.get("ARCADE_GIF_DIR_XMAS",        f"{_WALLART_BASE}/xmas-gifs"),
    "butterflies": os.environ.get("ARCADE_GIF_DIR_BUTTERFLIES", f"{_WALLART_BASE}/butterfly-gifs"),
    # add more categories here
}

# GPIO BCM pin numbers for each mode button (0 = disabled)
BTN_ART_PIN         = int(os.environ.get("ARCADE_BTN_ART_PIN",         "17"))
BTN_GAME_PIN        = int(os.environ.get("ARCADE_BTN_GAME_PIN",        "27"))
BTN_XMAS_PIN        = int(os.environ.get("ARCADE_BTN_XMAS_PIN",        "0"))
BTN_BUTTERFLIES_PIN = int(os.environ.get("ARCADE_BTN_BUTTERFLIES_PIN", "0"))

PYTHON = sys.executable
_ART = str(HERE / "modes" / "art.py")

# ── Mode definitions ────────────────────────────────────────────────────────
# Each mode is a command list passed to subprocess.Popen.
# GIF category modes all use the same art.py script with a different --dir.
MODES: dict[str, list[str]] = {
    "art": [
        PYTHON, _ART, "--dir", GIF_DIRS["art"],
    ],
    "xmas": [
        PYTHON, _ART, "--dir", GIF_DIRS["xmas"],
    ],
    "butterflies": [
        PYTHON, _ART, "--dir", GIF_DIRS["butterflies"],
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
        (BTN_ART_PIN,         "art"),
        (BTN_GAME_PIN,        "game"),
        (BTN_XMAS_PIN,        "xmas"),
        (BTN_BUTTERFLIES_PIN, "butterflies"),
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
            env = os.environ.copy()
            env.update({
                "ARCADE_LOG_DIR": LOG_DIR,
                "ARCADE_BRIGHTNESS": BRIGHTNESS,
                "ARCADE_LOOP_LENGTH": LOOP_LENGTH,
                "ARCADE_FRAME_DELAY": FRAME_DELAY,
            })
            self.current_proc = subprocess.Popen(MODES[mode], env=env)
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
