# Arcade LED Panel

A Raspberry Pi 5 powered 128×128 RGB LED matrix that switches between two modes via physical buttons:

- **Art mode** — plays animated GIFs from a directory in random order, one per minute
- **Game mode** — runs PICO-8 in splore via a virtual X display mirrored to the matrix

A `controller` daemon manages mode processes and watches GPIO buttons so you can switch modes without touching a keyboard.

## Hardware

| Component | Notes |
|---|---|
| Raspberry Pi 5 | Tested on Pi 5; Pi 4 would need `adafruit-blinka-raspberry-pi5-piomatter` equivalent |
| 128×128 RGB LED matrix | Built from two 64×64 HUB75 panels |
| Adafruit Matrix Bonnet | HUB75 driver HAT |
| Momentary push buttons | One per mode, wired to GPIO (see below) |

### Button wiring

Each button connects a GPIO pin to **GND**. The controller enables internal pull-up resistors, so no external resistors are needed.

```
GPIO pin ──┤ button ├── GND
```

Default pin assignments (configurable in `.env`):

| Button | GPIO (BCM) | Mode |
|---|---|---|
| Button 1 | 17 | Art |
| Button 2 | 27 | Game |

### Power button

For a dedicated power-off button, add this to `/boot/firmware/config.txt` and reboot:

```
dtoverlay=gpio-shutdown,gpio_pin=22
```

This is handled by the kernel directly and is more reliable than software shutdown.

## Software setup

### 1. Clone and configure

```bash
git clone <repo-url> ~/arcade
cd ~/arcade
cp .env.example .env
nano .env          # set paths and GPIO pins for your setup
```

### 2. Install Python dependencies

The project uses the `blinka_venv` virtual environment. Install into it:

```bash
source ~/.venvs/blinka_venv/bin/activate
pip install -r requirements.txt
```

### 3. Install the systemd service

```bash
bash scripts/install.sh
```

This renders `systemd/arcade.service` with your install path and user, copies it to `/etc/systemd/system/`, enables it, and starts it.

Check that it's running:

```bash
sudo systemctl status arcade
journalctl -u arcade -f      # live logs
```

## Directory layout

```
arcade/
├── controller.py       # mode manager daemon — watches GPIO, manages subprocesses
├── virtualdisplay.py   # mirrors a virtual X session to the LED matrix (game mode)
├── modes/
│   └── art.py          # GIF player (art mode)
├── systemd/
│   └── arcade.service  # service template (rendered by install.sh)
├── scripts/
│   ├── run.sh          # activates venv, launches controller
│   └── install.sh      # one-shot install helper
├── .env.example        # all configuration options with defaults
└── requirements.txt
```

GIF files are **not tracked in git** — store them in the directory pointed to by `ARCADE_GIF_DIR` (default: `~/wallart/wallart-gifs/`).

## Configuration reference

All options live in `.env` (copied from `.env.example`). Key settings:

| Variable | Default | Description |
|---|---|---|
| `ARCADE_GIF_DIR` | `~/wallart/wallart-gifs` | Directory of `.gif` files for art mode |
| `ARCADE_LOG_DIR` | `~/logs` | Where log files are written |
| `ARCADE_PICO8_BIN` | `~/pico-8/pico8_64` | Path to PICO-8 binary |
| `ARCADE_VENV` | `~/.venvs/blinka_venv` | Python venv used by `scripts/run.sh` |
| `ARCADE_BRIGHTNESS` | `0.5` | LED brightness (0.1 – 1.0) |
| `ARCADE_LOOP_LENGTH` | `60` | Seconds per GIF in art mode |
| `ARCADE_FRAME_DELAY` | `0.2` | Seconds between GIF frames |
| `ARCADE_DEFAULT_MODE` | `art` | Mode to start in on boot |
| `ARCADE_BTN_ART_PIN` | `17` | GPIO BCM pin for art button (0 = disabled) |
| `ARCADE_BTN_GAME_PIN` | `27` | GPIO BCM pin for game button (0 = disabled) |

## Adding modes

1. Create `modes/mymode.py` — any script that runs until killed via `SIGTERM`.
2. Add an entry to `MODES` in `controller.py`:
   ```python
   "mymode": [PYTHON, str(HERE / "modes" / "mymode.py")],
   ```
3. Add a button mapping in `controller.py` and the matching pin env var in `.env.example`.

For a seasonal GIF set (e.g. Christmas), you can reuse `modes/art.py` — just point `ARCADE_GIF_DIR` at the alternate directory and add a dedicated button that sets the env var before switching.

## Logs

| File | Contents |
|---|---|
| `logs/controller.log` | Mode switches, GPIO events, subprocess crashes |
| `logs/art.log` | Which GIF is playing, errors |

## Troubleshooting

**Matrix doesn't light up on boot** — check `journalctl -u arcade` and confirm the venv path in `.env` is correct.

**Buttons do nothing** — verify GPIO pin numbers with `pinout` (run in terminal) and check `controller.log` for GPIO errors. Pi 5 requires `lgpio`; install with `pip install lgpio`.

**PICO-8 game mode blank** — confirm the `ARCADE_PICO8_BIN` path is correct and that `xvfb` is installed (`sudo apt install xvfb`).
