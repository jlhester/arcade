# Arcade LED Panel

A Raspberry Pi 5 powered 128×128 RGB LED matrix that switches between several modes via physical buttons:

- **Wallart mode** — plays animated GIFs from `wallart-gifs` in random order, one per minute
- **Christmas mode** — same, from the `xmas-gifs` directory
- **Butterfly mode** — loops a single butterfly GIF continuously
- **Game mode** — runs PICO-8 in splore via a virtual X display mirrored to the matrix

A `controller` daemon manages mode processes and watches GPIO buttons so you can switch modes without touching a keyboard. Any mode can also be forced from the command line via systemd — see [Forcing a mode via systemd](#forcing-a-mode-via-systemd).

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
| Button 1 | 17 | Wallart |
| Button 2 | 27 | Game |

Christmas, butterflies, and butterfly buttons are disabled by default (pin `0`); set their pin env vars in `.env` to enable them.

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

This renders `systemd/arcade.service` **and** the `systemd/arcade@.service` template with your install path and user, copies both to `/etc/systemd/system/`, then enables and starts the button controller.

Check that it's running:

```bash
sudo systemctl status arcade
journalctl -u arcade -f      # live logs
```

### Forcing a mode via systemd

The button controller (`arcade.service`) is the default owner of the matrix. To pin the panel to one mode without touching a button, start a template instance — this stops the controller automatically:

```bash
sudo systemctl start arcade@game        # or wallart / christmas / butterflies / butterfly
sudo systemctl start arcade             # hand control back to the buttons
```

Only one process may drive the matrix at a time. `systemctl start arcade@<mode>` always stops the controller (via `Conflicts=`), but to switch directly between two forced modes use the helper, which stops every instance first:

```bash
sudo scripts/arcade-mode.sh christmas
```

## Directory layout

```
arcade/
├── controller.py       # mode manager daemon — watches GPIO, manages subprocesses
├── virtualdisplay.py   # mirrors a virtual X session to the LED matrix (game mode)
├── modes/
│   └── art.py          # GIF player (art mode)
├── systemd/
│   ├── arcade.service   # button controller unit (rendered by install.sh)
│   └── arcade@.service  # per-mode template unit: arcade@<mode> (rendered by install.sh)
├── scripts/
│   ├── run.sh          # activates venv, launches controller (or one mode)
│   ├── arcade-mode.sh  # force a single mode via systemd
│   └── install.sh      # one-shot install helper
├── .env.example        # all configuration options with defaults
└── requirements.txt
```

GIF files are **not tracked in git** — store them in the directory pointed to by `ARCADE_GIF_DIR_WALLART` (default: `~/wallart/wallart-gifs/`).

## Configuration reference

All options live in `.env` (copied from `.env.example`). Key settings:

| Variable | Default | Description |
|---|---|---|
| `ARCADE_GIF_DIR_WALLART` | `~/wallart/wallart-gifs` | Directory of `.gif` files for wallart mode |
| `ARCADE_GIF_DIR_CHRISTMAS` | `~/wallart/xmas-gifs` | Directory of `.gif` files for christmas mode |
| `ARCADE_GIF_DIR_BUTTERFLIES` | `~/wallart/butterfly-gifs` | Directory of `.gif` files for butterflies mode |
| `ARCADE_BUTTERFLY_GIF` | `~/wallart/butterfly-gifs/butterfly.gif` | Single GIF looped by butterfly mode |
| `ARCADE_LOG_DIR` | `~/logs` | Where log files are written |
| `ARCADE_PICO8_BIN` | `~/pico-8/pico8_64` | Path to PICO-8 binary |
| `ARCADE_VENV` | `~/.venvs/blinka_venv` | Python venv used by `scripts/run.sh` |
| `ARCADE_BRIGHTNESS` | `0.5` | LED brightness (0.1 – 1.0) |
| `ARCADE_LOOP_LENGTH` | `60` | Seconds per GIF in directory (wallart/christmas) modes |
| `ARCADE_FRAME_DELAY` | `0.2` | Seconds between GIF frames |
| `ARCADE_DEFAULT_MODE` | `wallart` | Mode to start in on boot |
| `ARCADE_BTN_WALLART_PIN` | `17` | GPIO BCM pin for wallart button (0 = disabled) |
| `ARCADE_BTN_GAME_PIN` | `27` | GPIO BCM pin for game button (0 = disabled) |
| `ARCADE_BTN_CHRISTMAS_PIN` | `0` | GPIO BCM pin for christmas button (0 = disabled) |
| `ARCADE_BTN_BUTTERFLIES_PIN` | `0` | GPIO BCM pin for butterflies button (0 = disabled) |
| `ARCADE_BTN_BUTTERFLY_PIN` | `0` | GPIO BCM pin for butterfly button (0 = disabled) |

## Adding modes

1. Create `modes/mymode.py` — any script that runs until killed via `SIGTERM`.
2. Add an entry to `MODES` in `controller.py`:
   ```python
   "mymode": [PYTHON, str(HERE / "modes" / "mymode.py")],
   ```
3. Add a button mapping in `controller.py` and the matching pin env var in `.env.example`.

For a seasonal GIF set, reuse `modes/art.py` with a different `--dir` (see the `wallart`/`christmas` entries in `MODES`), or `--file` to loop a single GIF (see `butterfly`). Every mode name is also reachable via `arcade@<mode>` with no extra work.

## Logs

| File | Contents |
|---|---|
| `logs/controller.log` | Mode switches, GPIO events, subprocess crashes |
| `logs/art.log` | Which GIF is playing, errors |

## Troubleshooting

**Matrix doesn't light up on boot** — check `journalctl -u arcade` and confirm the venv path in `.env` is correct.

**Buttons do nothing** — verify GPIO pin numbers with `pinout` (run in terminal) and check `controller.log` for GPIO errors. Pi 5 requires `lgpio`; install with `pip install lgpio`.

**PICO-8 game mode blank** — confirm the `ARCADE_PICO8_BIN` path is correct and that `xvfb` is installed (`sudo apt install xvfb`).
