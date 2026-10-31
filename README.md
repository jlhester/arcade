# Arcade LED Panel

A Raspberry Pi 5 powered 128×128 RGB LED matrix that runs one of several modes:

- **Wallart mode** — plays animated GIFs from `wallart-gifs` in random order, one per minute
- **Christmas mode** — same, from the `xmas-gifs` directory
- **Halloween mode** — same, from the `halloween-gifs` directory
- **Butterfly mode** — loops a single butterfly GIF continuously
- **Game mode** — runs PICO-8 in splore via a virtual X display mirrored to the matrix

A `controller` daemon manages the mode processes. **Right now the panel is driven entirely over systemd from the command line** — no physical buttons are wired yet ([Current state](#current-state-control-via-systemd-no-buttons)). Once the button board is built, the same daemon switches modes on GPIO presses, with systemd still available as an override ([State once buttons installed](#state-once-buttons-installed)).

## Hardware

| Component | Notes |
|---|---|
| Raspberry Pi 5 | Tested on Pi 5; Pi 4 would need `adafruit-blinka-raspberry-pi5-piomatter` equivalent |
| 128×128 RGB LED matrix | Built from two 64×64 HUB75 panels |
| Adafruit Matrix Bonnet | HUB75 driver HAT |
| Momentary push buttons | One per mode, wired to GPIO — **not yet wired; see [State once buttons installed](#state-once-buttons-installed)** |

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

Christmas, halloween, butterflies, and butterfly buttons are disabled by default (pin `0`); set their pin env vars in `.env` to enable them.

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

## Current state: control via systemd (no buttons)

No buttons are wired, so `ARCADE_BTN_*_PIN` are all `0` in `.env`. The controller (`arcade.service`) skips GPIO entirely and just boots into `ARCADE_DEFAULT_MODE` (default: `wallart`). You switch modes from the command line.

Only one process may drive the matrix at a time, so starting a `arcade@<mode>` template instance automatically stops whatever was running (via `Conflicts=`):

```bash
sudo systemctl start arcade@wallart      # all wallart-gifs, random rotation
sudo systemctl start arcade@christmas    # all xmas-gifs, random rotation
sudo systemctl start arcade@halloween    # all halloween-gifs, random rotation
sudo systemctl start arcade@butterfly    # single butterfly.gif, looped forever
sudo systemctl start arcade@game         # PICO-8 in splore
sudo systemctl start arcade@butterflies  # (the whole butterfly-gifs directory)
```

To return to the boot behaviour — the plain controller, which without buttons just sits in `ARCADE_DEFAULT_MODE`:

```bash
sudo systemctl start arcade
```

When switching **directly between two forced modes**, use the helper instead of two `start` commands — it stops every instance first so two processes never fight over the panel:

```bash
sudo scripts/arcade-mode.sh butterfly
```

See what's active and follow logs:

```bash
systemctl status 'arcade*'
journalctl -u 'arcade@*' -f
```

**Reboot behaviour:** `arcade@<mode>` instances are not enabled, so they don't survive a reboot — on boot the panel always returns to `arcade.service` running `ARCADE_DEFAULT_MODE`. To change the boot mode, set `ARCADE_DEFAULT_MODE` in `.env` and `sudo systemctl restart arcade`.

## State once buttons installed

When the button board is built, each mode gets a physical button and the controller switches modes on GPIO presses. The systemd commands above still work as an override. **None of this needs a reinstall — buttons are pure `.env` config picked up on restart.**

1. **Wire each button.** Connect one momentary push button per mode between its GPIO pin and **GND**. The controller enables internal pull-ups, so no external resistors are needed:
   ```
   GPIO pin ──┤ button ├── GND
   ```
2. **Pick a pin per mode** and set the matching env vars in `.env`. Every mode has a button slot; `0` means disabled. Suggested assignments:

   | `.env` variable | Mode | Suggested pin (BCM) |
   |---|---|---|
   | `ARCADE_BTN_WALLART_PIN` | wallart | 17 |
   | `ARCADE_BTN_GAME_PIN` | game | 27 |
   | `ARCADE_BTN_CHRISTMAS_PIN` | christmas | *(choose)* |
   | `ARCADE_BTN_HALLOWEEN_PIN` | halloween | *(choose)* |
   | `ARCADE_BTN_BUTTERFLIES_PIN` | butterflies | *(choose)* |
   | `ARCADE_BTN_BUTTERFLY_PIN` | butterfly | *(choose)* |

   Give every enabled button a **unique** pin. Verify pin numbering with `pinout` in a terminal. (Pi 5 requires the `lgpio` pin factory, already set via `GPIOZERO_PIN_FACTORY=lgpio`.)
3. **Apply it:**
   ```bash
   sudo systemctl restart arcade
   ```
4. **Verify.** `journalctl -u arcade -f` should log a `Button on GPIO <pin> → <mode> mode` line for each enabled button at startup. Press each button and confirm the panel switches.
5. **(Optional) power-off button** — see [Power button](#power-button) above: add `dtoverlay=gpio-shutdown,gpio_pin=22` to `/boot/firmware/config.txt` (the Bonnet's J2 header can also handle graceful shutdown natively).

**Gotchas:**
- Buttons only work while the **button controller** (`arcade.service`) is the active owner. If you've forced a mode with `sudo systemctl start arcade@<mode>`, the controller is stopped and buttons do nothing until you run `sudo systemctl start arcade` again.
- Remember to change the pin values away from `0` — leaving a pin at `0` keeps that button disabled even if it's physically wired.

## Directory layout

```
arcade/
├── controller.py       # mode manager daemon — watches GPIO, manages subprocesses
├── virtualdisplay.py   # mirrors a virtual X session to the LED matrix (game mode)
├── modes/
│   └── art.py          # GIF player: --dir (wallart/christmas) or --file (butterfly)
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
| `ARCADE_GIF_DIR_HALLOWEEN` | `~/wallart/halloween-gifs` | Directory of `.gif` files for halloween mode |
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
| `ARCADE_BTN_HALLOWEEN_PIN` | `0` | GPIO BCM pin for halloween button (0 = disabled) |
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
