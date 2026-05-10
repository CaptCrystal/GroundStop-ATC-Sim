"""Shared logger for the audio subsystem (TTS + STT).

Writes to  logs/audio.log  at DEBUG level.
Also echoes INFO+ to the console so startup messages remain visible.
propagate=False keeps audio noise out of aircraft_debug.log.
"""

import logging
import sys
from pathlib import Path

_LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
_LOG_DIR.mkdir(exist_ok=True)

_FMT = logging.Formatter(
    "%(asctime)s.%(msecs)03d  %(levelname)-7s  %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

def _get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured (reimport guard)

    logger.setLevel(logging.DEBUG)
    logger.propagate = False   # don't bleed into aircraft_debug.log

    # File — full DEBUG detail
    fh = logging.FileHandler(_LOG_DIR / "audio.log", mode="a", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(_FMT)
    logger.addHandler(fh)

    # Console — INFO and above only
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(_FMT)
    logger.addHandler(sh)

    return logger
