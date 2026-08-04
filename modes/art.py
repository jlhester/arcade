#!/usr/bin/env python3
"""
Art mode: plays GIFs from a directory in random order, spending ARCADE_LOOP_LENGTH
seconds on each before moving to the next. Cycles through all GIFs before repeating.

With --file, plays a single GIF on an endless loop instead (butterfly mode).

Usage:
    python art.py                          # uses ARCADE_GIF_DIR env var
    python art.py --dir /path/to/xmas-gifs
    python art.py --file /path/to/butterfly.gif
"""
import argparse
import logging
import os
import random
import sys
import time

import numpy as np
from PIL import Image, ImageEnhance

import adafruit_blinka_raspberry_pi5_piomatter as piomatter

_parser = argparse.ArgumentParser()
_parser.add_argument(
    "--dir",
    default=os.environ.get("ARCADE_GIF_DIR", "/home/arcadeuser/wallart/wallart-gifs"),
    help="Directory of GIF files to play (overrides ARCADE_GIF_DIR)",
)
_parser.add_argument(
    "--file",
    default=None,
    help="Play a single GIF on an endless loop (overrides --dir)",
)
_args = _parser.parse_args()

GIF_DIR = _args.dir
LOG_DIR = os.environ.get("ARCADE_LOG_DIR", "/home/arcadeuser/logs")
BRIGHTNESS = float(os.environ.get("ARCADE_BRIGHTNESS", "0.5"))
LOOP_LENGTH = int(os.environ.get("ARCADE_LOOP_LENGTH", "60"))
FRAME_DELAY = float(os.environ.get("ARCADE_FRAME_DELAY", "0.2"))

WIDTH = 128
HEIGHT = 128

os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "art.log")),
        logging.StreamHandler(),
    ],
    level=logging.INFO,
)
logger = logging.getLogger("art")

canvas = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
geometry = piomatter.Geometry(
    width=WIDTH, height=HEIGHT, n_addr_lines=5, rotation=piomatter.Orientation.Normal
)
framebuffer = np.asarray(canvas) + 0
matrix = piomatter.PioMatter(
    colorspace=piomatter.Colorspace.RGB888Packed,
    pinout=piomatter.Pinout.AdafruitMatrixBonnet,
    framebuffer=framebuffer,
    geometry=geometry,
)

def _show_frame(frame):
    if BRIGHTNESS != 1.0:
        frame = ImageEnhance.Brightness(frame).enhance(BRIGHTNESS)
    canvas.paste(frame, (0, 0))
    framebuffer[:] = np.asarray(canvas)
    matrix.show()
    time.sleep(FRAME_DELAY)


def play_single(gif_file: str) -> None:
    """Play one GIF on an endless loop until the process is killed."""
    if not os.path.isfile(gif_file):
        logger.error("GIF not found: %s", gif_file)
        sys.exit(1)
    logger.info("Butterfly mode started: looping %s", gif_file)
    while True:
        try:
            with Image.open(gif_file) as img:
                for frame_idx in range(img.n_frames):
                    img.seek(frame_idx)
                    _show_frame(img.resize((WIDTH, HEIGHT)))
        except Exception:
            logger.exception("Error playing %s", gif_file)
            time.sleep(1)


def play_directory(gif_dir: str) -> None:
    """Play every GIF in a directory in random order, LOOP_LENGTH seconds each."""
    gifs = [f for f in os.listdir(gif_dir) if f.lower().endswith(".gif")]
    if not gifs:
        logger.error("No GIFs found in %s", gif_dir)
        sys.exit(1)

    logger.info("Art mode started: %d GIFs in %s", len(gifs), gif_dir)
    seen: set[int] = set()

    while True:
        if len(seen) >= len(gifs):
            seen = set()

        gif_index = random.choice(list(set(range(len(gifs))) - seen))
        seen.add(gif_index)
        gif_file = os.path.join(gif_dir, gifs[gif_index])

        try:
            with Image.open(gif_file) as img:
                logger.info("Playing %s", gifs[gif_index])
                start_time = time.time()
                while time.time() - start_time < LOOP_LENGTH:
                    for frame_idx in range(1, img.n_frames):
                        img.seek(frame_idx)
                        _show_frame(img.resize((WIDTH, HEIGHT)))
                        if time.time() - start_time >= LOOP_LENGTH:
                            break
        except Exception:
            logger.exception("Error playing %s", gif_file)


if _args.file:
    play_single(_args.file)
else:
    play_directory(GIF_DIR)
