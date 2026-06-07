"""Screen capture via grim (Wayland/wlroots)."""

import asyncio
import os
import tempfile
import logging

log = logging.getLogger(__name__)


async def capture_screenshot() -> bytes:
    """Capture a full-screen PNG screenshot via grim.

    Returns PNG bytes. Raises RuntimeError on failure.
    Requires `grim` to be installed (apt install grim or similar).
    """
    # Create temp file for the screenshot
    fd, tmp_path = tempfile.mkstemp(suffix=".png")
    os.close(fd)

    try:
        proc = await asyncio.create_subprocess_exec(
            "grim", tmp_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            err_msg = stderr.decode().strip() if stderr else "unknown error"
            raise RuntimeError(f"grim failed (exit {proc.returncode}): {err_msg}")

        with open(tmp_path, "rb") as f:
            data = f.read()

        if len(data) < 100:
            raise RuntimeError(f"Screenshot too small ({len(data)} bytes)")

        log.info("Captured screenshot: %d bytes", len(data))
        return data

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
