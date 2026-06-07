"""Detector V0 — main orchestration loop."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
import threading

from . import analyzer, audio_capture, screen_capture
from .tray_icon import TrayIndicator

log = logging.getLogger(__name__)

# How often to run the analysis cycle (seconds)
ANALYSIS_INTERVAL = 30.0

# How long to record audio each cycle (seconds)
AUDIO_DURATION = 5.0


async def analysis_cycle(tray: TrayIndicator) -> None:
    """Run one capture-and-analyze cycle."""
    log.info("Starting analysis cycle")

    # Capture screenshot and audio in parallel
    screenshot_task = asyncio.create_task(screen_capture.capture_screenshot())
    audio_task = asyncio.create_task(audio_capture.record_audio(AUDIO_DURATION))

    # Screenshot completes quickly; audio takes AUDIO_DURATION seconds
    screenshot_png = await screenshot_task
    audio_wav = await audio_task

    # Analyze with Gemini
    result = await analyzer.analyze(screenshot_png, audio_wav)

    # Update tray icon
    if result.is_distracting:
        log.warning("DISTRACTING: %s", result.reason)
        tray.set_distracting(result.reason)
    else:
        log.info("OK: %s", result.reason[:80] if result.reason else "productive")
        tray.set_ok()


async def run_loop(tray: TrayIndicator, stop_event: asyncio.Event) -> None:
    """Run the analysis loop until stop_event is set."""
    log.info(
        "Analysis loop started (interval=%.0fs, audio=%.0fs)",
        ANALYSIS_INTERVAL,
        AUDIO_DURATION,
    )

    while not stop_event.is_set():
        try:
            await analysis_cycle(tray)
        except Exception:
            log.exception("Analysis cycle failed")

        # Wait for the interval, but break early if stopped
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=ANALYSIS_INTERVAL)
        except asyncio.TimeoutError:
            pass  # normal — interval elapsed, run next cycle


def main() -> None:
    """Entry point. Starts the tray icon and analysis loop."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    log.info("Detector V0 starting")

    tray = TrayIndicator()
    stop_event = asyncio.Event()

    def request_stop():
        """Signal the async loop to stop."""
        log.info("Stop requested")
        stop_event.set()

    tray.on_quit(request_stop)

    # Run the async analysis loop in a background thread
    def run_async_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Handle SIGINT/SIGTERM in the async loop
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, request_stop)

        try:
            loop.run_until_complete(run_loop(tray, stop_event))
        finally:
            loop.close()

        # When the async loop finishes, quit the GTK loop
        tray.quit()

    thread = threading.Thread(target=run_async_loop, daemon=True)
    thread.start()

    # GTK main loop runs on the main thread (required by GTK)
    try:
        tray.run()
    except KeyboardInterrupt:
        request_stop()

    thread.join(timeout=10)
    log.info("Detector V0 stopped")


if __name__ == "__main__":
    main()
