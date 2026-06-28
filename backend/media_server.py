"""MediaMTX subprocess lifecycle management"""
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---- paths ----
BASE_DIR = Path(__file__).resolve().parent
BIN_DIR = BASE_DIR / "bin"
MEDIAMTX_EXE = BIN_DIR / "mediamtx.exe"
MEDIAMTX_YML = BASE_DIR / "mediamtx.yml"

_process: Optional[subprocess.Popen] = None


def _find_mediamtx() -> str:
    """Find mediamtx executable."""
    candidates = [
        MEDIAMTX_EXE,
        BIN_DIR / "mediamtx",
        BASE_DIR / "mediamtx.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    raise FileNotFoundError(
        f"MediaMTX not found. Please place mediamtx.exe in {BIN_DIR}"
    )


def start_mediamtx() -> None:
    """Launch MediaMTX as a background subprocess."""
    global _process

    if _process is not None and _process.poll() is None:
        logger.info("MediaMTX is already running")
        return

    # Kill any zombie MediaMTX processes from previous runs
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "mediamtx.exe"],
                capture_output=True, timeout=5,
            )
        except Exception:
            pass

    exe = _find_mediamtx()
    config = str(MEDIAMTX_YML)

    if not MEDIAMTX_YML.exists():
        logger.warning(f"Config not found at {config}, using bin/ default")
        config = str(BIN_DIR / "mediamtx.yml")

    logger.info(f"Starting MediaMTX: {exe} {config}")

    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    _process = subprocess.Popen(
        [exe, config],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(BASE_DIR),
        **kwargs,
    )

    time.sleep(1.5)
    if _process.poll() is not None:
        out = ""
        if _process.stdout:
            out = _process.stdout.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"MediaMTX exited early: {out}")

    logger.info(f"MediaMTX started (PID {_process.pid})")


def stop_mediamtx() -> None:
    """Gracefully terminate MediaMTX."""
    global _process

    if _process is None:
        return

    logger.info("Stopping MediaMTX...")
    try:
        if sys.platform == "win32":
            _process.terminate()
        else:
            _process.send_signal(signal.SIGINT)
        _process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        logger.warning("MediaMTX did not stop, force killing")
        _process.kill()
        _process.wait(timeout=3)
    except Exception as e:
        logger.warning(f"Error stopping MediaMTX: {e}")

    _process = None
    logger.info("MediaMTX stopped")


def is_media_ready() -> bool:
    return _process is not None and _process.poll() is None
