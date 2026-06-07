#!/usr/bin/env python3
"""Detector V0 — distraction detector for Linux desktops.

Periodically captures a screenshot (via XDG Desktop Portal) and audio
(via pw-record), sends both to Gemini 3.1 Flash-Lite for analysis, and
shows a system tray cross icon: green = productive, red = distracting.

Usage:
    python detector.py

System dependencies:
    pw-record                          PipeWire audio recorder
    python3-gi                         PyGObject
    gir1.2-ayatanaappindicator3-0.1    Tray indicator

Python dependencies:
    pip install 'pydantic-ai[google]'

Secrets:
    ~/.agents/secrets/google_ai_studio   Google AI Studio API key
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlparse

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")

from gi.repository import AyatanaAppIndicator3, Gio, GLib, Gtk  # noqa: E402

_session_bus: Gio.DBusConnection | None = None


def _get_session_bus() -> Gio.DBusConnection:
    """Lazy singleton for the session D-Bus connection."""
    global _session_bus
    if _session_bus is None:
        _session_bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    return _session_bus
from pydantic_ai import Agent, BinaryContent, RunContext  # noqa: E402

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ANALYSIS_INTERVAL = 30.0   # seconds between analysis cycles
AUDIO_DURATION = 5.0       # seconds of audio per cycle

SECRETS_DIR = Path.home() / ".agents" / "secrets"
GEMINI_MODEL = "google-gla:gemini-3.1-flash-lite"

ICONS_DIR = Path(__file__).resolve().parent / "icons"
ICON_GREEN = str(ICONS_DIR / "green")   # AppIndicator appends .svg/.png
ICON_RED = str(ICONS_DIR / "red")

SYSTEM_PROMPT = """\
You are a distraction detector. You will receive a screenshot of a user's screen
and a short audio clip from their environment.

Your job is to determine whether the user is currently engaged in distracting
content — things like social media feeds, entertainment videos, games, or
non-work browsing.

If the content IS distracting, call the `flag_distracting` tool with a brief
reason explaining why.

If the content is NOT distracting (e.g., code editor, terminal, documentation,
work-related content), do NOT call the tool — just respond briefly confirming
the content looks productive.

Be conservative: only flag things that are clearly recreational or off-task.
Ambiguous content should NOT be flagged.
"""

# ---------------------------------------------------------------------------
# Screen capture (GNOME Wayland — silent, no flash)
# ---------------------------------------------------------------------------


def _screenshot_gnome_shell(tmp_path: str) -> bool:
    """Try org.gnome.Shell.Screenshot (no flash, no UI). Returns True on success."""
    try:
        result = _get_session_bus().call_sync(
            "org.gnome.Shell.Screenshot",
            "/org/gnome/Shell/Screenshot",
            "org.gnome.Shell.Screenshot",
            "Screenshot",
            GLib.Variant("(bbs)", (False, False, tmp_path)),
            GLib.VariantType("(bs)"),
            Gio.DBusCallFlags.NONE,
            10000,
            None,
        )
        success, _path = result.unpack()
        return success
    except Exception as e:
        log.debug("GNOME Shell screenshot unavailable: %s", e)
        return False


_portal_token_counter = 0


def _screenshot_portal(tmp_path: str) -> bool:
    """Fallback: XDG Desktop Portal Screenshot (interactive=false).

    Subscribes to the Response signal BEFORE making the call so we never
    miss a fast reply.
    """
    global _portal_token_counter
    _portal_token_counter += 1

    bus = _get_session_bus()
    result_event = threading.Event()
    captured: dict[str, str | None] = {"uri": None}

    # Build a predictable request path so we can subscribe before calling
    sender = bus.get_unique_name().lstrip(":").replace(".", "_")
    handle_token = f"detector_v0_{_portal_token_counter}"
    request_path = f"/org/freedesktop/portal/desktop/request/{sender}/{handle_token}"

    def on_response(_conn, _sender, _path, _iface, _signal, params):
        response, results = params.unpack()
        if response == 0:
            captured["uri"] = results["uri"]
        result_event.set()

    # Subscribe FIRST — before making the portal call
    sub_id = bus.signal_subscribe(
        "org.freedesktop.portal.Desktop",
        "org.freedesktop.portal.Request",
        "Response",
        request_path,
        None,
        Gio.DBusSignalFlags.NONE,
        on_response,
    )

    try:
        bus.call_sync(
            "org.freedesktop.portal.Desktop",
            "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.Screenshot",
            "Screenshot",
            GLib.Variant("(sa{sv})", ("", {
                "interactive": GLib.Variant("b", False),
                "handle_token": GLib.Variant("s", handle_token),
            })),
            GLib.VariantType("(o)"),
            Gio.DBusCallFlags.NONE,
            10000,
            None,
        )
    except Exception as e:
        bus.signal_unsubscribe(sub_id)
        log.error("Portal Screenshot call failed: %s", e)
        return False

    result_event.wait(timeout=10.0)
    bus.signal_unsubscribe(sub_id)

    if captured["uri"] is None:
        return False

    # Portal saves its own file; copy to our tmp_path
    src = unquote(urlparse(captured["uri"]).path)
    try:
        with open(src, "rb") as fsrc, open(tmp_path, "wb") as fdst:
            fdst.write(fsrc.read())
    finally:
        try:
            os.unlink(src)
        except OSError:
            pass
    return True


async def capture_screenshot() -> bytes:
    """Capture a full-screen PNG screenshot (silent, no flash).

    Tries GNOME Shell D-Bus first, falls back to XDG portal.
    Returns PNG bytes.
    """
    fd, tmp_path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        loop = asyncio.get_running_loop()
        ok = await loop.run_in_executor(None, _screenshot_gnome_shell, tmp_path)
        if not ok:
            log.info("GNOME Shell screenshot denied, trying portal fallback")
            ok = await loop.run_in_executor(None, _screenshot_portal, tmp_path)
        if not ok:
            raise RuntimeError("All screenshot methods failed")
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


# ---------------------------------------------------------------------------
# Audio capture
# ---------------------------------------------------------------------------


async def record_audio(duration_secs: float = AUDIO_DURATION) -> bytes:
    """Record audio via pw-record for the given duration.

    Returns WAV bytes (signed 16-bit, 16 kHz, mono).
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
        await asyncio.sleep(duration_secs)
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


# ---------------------------------------------------------------------------
# AI analysis (Pydantic AI + Gemini)
# ---------------------------------------------------------------------------


@dataclass
class AnalysisResult:
    """Result of a distraction analysis."""
    is_distracting: bool = False
    reason: str = ""


@dataclass
class _AnalysisDeps:
    """Mutable state passed through the agent run."""
    result: AnalysisResult = field(default_factory=AnalysisResult)


def _load_api_key() -> str:
    key_file = SECRETS_DIR / "google_ai_studio"
    if not key_file.exists():
        raise RuntimeError(
            f"Gemini API key not found at {key_file}. "
            f"Place your Google AI Studio key in {key_file}"
        )
    return key_file.read_text().strip()


def _make_agent() -> Agent[_AnalysisDeps, str]:
    os.environ.setdefault("GOOGLE_API_KEY", _load_api_key())

    agent: Agent[_AnalysisDeps, str] = Agent(
        GEMINI_MODEL,
        deps_type=_AnalysisDeps,
        system_prompt=SYSTEM_PROMPT,
    )

    @agent.tool
    async def flag_distracting(ctx: RunContext[_AnalysisDeps], reason: str) -> str:
        """Flag the current screen/audio content as distracting.

        Args:
            reason: Brief explanation of why the content is distracting.
        """
        ctx.deps.result.is_distracting = True
        ctx.deps.result.reason = reason
        log.info("Content flagged as distracting: %s", reason)
        return f"Flagged as distracting: {reason}"

    return agent


_agent: Agent[_AnalysisDeps, str] | None = None


def _get_agent() -> Agent[_AnalysisDeps, str]:
    global _agent
    if _agent is None:
        _agent = _make_agent()
    return _agent


async def analyze(
    screenshot_png: bytes,
    audio_wav: bytes | None = None,
) -> AnalysisResult:
    """Analyze a screenshot (and optional audio) for distracting content."""
    agent = _get_agent()
    deps = _AnalysisDeps()

    user_prompt: list[str | BinaryContent] = [
        "Analyze this screenshot and audio for distracting content.",
        BinaryContent(data=screenshot_png, media_type="image/png"),
    ]
    if audio_wav and len(audio_wav) > 1000:
        user_prompt.append(BinaryContent(data=audio_wav, media_type="audio/wav"))

    try:
        result = await agent.run(user_prompt, deps=deps)
        log.info("Analysis complete. Distracting: %s", deps.result.is_distracting)
        if not deps.result.is_distracting:
            deps.result.reason = result.output
    except Exception as e:
        log.error("Analysis failed: %s", e)
        deps.result.reason = f"Analysis error: {e}"

    return deps.result


# ---------------------------------------------------------------------------
# Tray icon
# ---------------------------------------------------------------------------


class TrayIndicator:
    """System tray cross indicator. Green = OK, red = distracting."""

    def __init__(self) -> None:
        self._indicator = AyatanaAppIndicator3.Indicator.new(
            "detector-v0",
            ICON_GREEN,
            AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self._indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)

        menu = Gtk.Menu()
        self._status_item = Gtk.MenuItem(label="Status: OK")
        self._status_item.set_sensitive(False)
        menu.append(self._status_item)
        menu.append(Gtk.SeparatorMenuItem())
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self._on_quit)
        menu.append(quit_item)
        menu.show_all()
        self._indicator.set_menu(menu)

        self._quit_callback: callable | None = None
        log.info("Tray indicator initialized (green)")

    def set_ok(self) -> None:
        GLib.idle_add(self._set_ok_internal)

    def _set_ok_internal(self) -> bool:
        self._indicator.set_icon_full(ICON_GREEN, "OK")
        self._status_item.set_label("Status: OK")
        return False

    def set_distracting(self, reason: str = "") -> None:
        GLib.idle_add(self._set_distracting_internal, reason)

    def _set_distracting_internal(self, reason: str) -> bool:
        self._indicator.set_icon_full(ICON_RED, "Distracting")
        label = f"Distracting: {reason}" if reason else "Status: Distracting"
        if len(label) > 60:
            label = label[:57] + "..."
        self._status_item.set_label(label)
        return False

    def on_quit(self, callback: callable) -> None:
        self._quit_callback = callback

    def _on_quit(self, _widget) -> None:
        log.info("Quit requested from tray menu")
        if self._quit_callback:
            self._quit_callback()
        Gtk.main_quit()

    def run(self) -> None:
        log.info("Starting GTK main loop")
        Gtk.main()

    def quit(self) -> None:
        GLib.idle_add(Gtk.main_quit)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


async def analysis_cycle(tray: TrayIndicator) -> None:
    """Run one capture-and-analyze cycle."""
    log.info("Starting analysis cycle")

    screenshot_task = asyncio.create_task(capture_screenshot())
    audio_task = asyncio.create_task(record_audio(AUDIO_DURATION))

    screenshot_png = await screenshot_task
    audio_wav = await audio_task

    result = await analyze(screenshot_png, audio_wav)

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
        ANALYSIS_INTERVAL, AUDIO_DURATION,
    )
    while not stop_event.is_set():
        try:
            await analysis_cycle(tray)
        except Exception:
            log.exception("Analysis cycle failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=ANALYSIS_INTERVAL)
        except asyncio.TimeoutError:
            pass


def main() -> None:
    """Entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    log.info("Detector V0 starting")

    tray = TrayIndicator()
    stop_event = asyncio.Event()

    def request_stop():
        log.info("Stop requested")
        stop_event.set()

    def shutdown():
        request_stop()
        tray.quit()

    tray.on_quit(shutdown)

    # Let Ctrl+C trigger a clean shutdown through the GLib main loop
    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGINT, shutdown)
    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGTERM, shutdown)

    def run_async_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_loop(tray, stop_event))
        finally:
            loop.close()

    thread = threading.Thread(target=run_async_loop, daemon=True)
    thread.start()

    tray.run()  # blocks until GTK quits

    thread.join(timeout=10)
    log.info("Detector V0 stopped")


if __name__ == "__main__":
    main()
