"""System tray indicator — cross icon, green (OK) or red (distracting)."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")

from gi.repository import AyatanaAppIndicator3, GLib, Gtk  # noqa: E402

log = logging.getLogger(__name__)

# Icon paths — SVG files next to the source
ICONS_DIR = Path(__file__).resolve().parent.parent.parent / "icons"
ICON_GREEN = str(ICONS_DIR / "green")  # AppIndicator appends .svg/.png
ICON_RED = str(ICONS_DIR / "red")


class TrayIndicator:
    """System tray cross indicator.

    Green = productive/OK.  Red = distracting.

    Must call `run()` from the main thread (GTK main loop).
    Other methods are thread-safe via GLib.idle_add.
    """

    def __init__(self) -> None:
        self._indicator = AyatanaAppIndicator3.Indicator.new(
            "detector-v0",
            ICON_GREEN,
            AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self._indicator.set_status(
            AyatanaAppIndicator3.IndicatorStatus.ACTIVE
        )

        # Minimal menu (GTK requires at least one menu item)
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
        """Set the icon to green (productive)."""
        GLib.idle_add(self._set_ok_internal)

    def _set_ok_internal(self) -> bool:
        self._indicator.set_icon_full(ICON_GREEN, "OK")
        self._status_item.set_label("Status: OK")
        return False  # run once

    def set_distracting(self, reason: str = "") -> None:
        """Set the icon to red (distracting)."""
        GLib.idle_add(self._set_distracting_internal, reason)

    def _set_distracting_internal(self, reason: str) -> bool:
        self._indicator.set_icon_full(ICON_RED, "Distracting")
        label = f"Distracting: {reason}" if reason else "Status: Distracting"
        # Truncate long reasons for the menu
        if len(label) > 60:
            label = label[:57] + "..."
        self._status_item.set_label(label)
        return False

    def on_quit(self, callback: callable) -> None:
        """Register a callback to be called when the user clicks Quit."""
        self._quit_callback = callback

    def _on_quit(self, _widget) -> None:
        log.info("Quit requested from tray menu")
        if self._quit_callback:
            self._quit_callback()
        Gtk.main_quit()

    def run(self) -> None:
        """Start the GTK main loop. Blocks until quit."""
        log.info("Starting GTK main loop")
        Gtk.main()

    def quit(self) -> None:
        """Quit the GTK main loop from any thread."""
        GLib.idle_add(Gtk.main_quit)
