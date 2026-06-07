"""Audio capture via pw-record (PipeWire)."""

import asyncio
import os
import signal
import tempfile
import logging

log = logging.getLogger(__name__)


async def record_audio(duration_secs: float = 5.0) -> bytes:
    """Record audio via pw-record for the given duration.

    Returns WAV bytes (signed 16-bit, 16kHz, mono).
    Raises RuntimeError on failure.
    Requires `pw-record` (PipeWire) to be installed.
    """
    fd, tmp_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)

    try:
        proc = await asyncio.create_subprocess_exec(
            "pw-record", "--format=s16", "--rate=16000", "--channels=1", tmp_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

        log.info("Recording audio for %.1fs...", duration_secs)

        # Let it record for the specified duration
        await asyncio.sleep(duration_secs)

        # Stop recording gracefully with SIGINT
        proc.send_signal(signal.SIGINT)
        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()

        with open(tmp_path, "rb") as f:
            data = f.read()

        if len(data) < 1000:
            log.warning("Audio recording very small: %d bytes", len(data))

        log.info("Recorded audio: %d bytes", len(data))
        return data

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
