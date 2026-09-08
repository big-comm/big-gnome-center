# SPDX-License-Identifier: MIT
"""Reload managed GTK material in cooperating windows."""

import os
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

if __package__:
    from .policy import NAME, OWNER, gtk_supports_blur
else:
    from window_material import NAME, OWNER, gtk_supports_blur


def attach_window_material(window, css_class):
    """Attach optional material and release it with the window."""
    client = WindowMaterialClient(window, css_class)
    window.connect("destroy", lambda *_args: client.close(remove_class=False))
    return client


class WindowMaterialClient:
    def __init__(self, window, css_class):
        self._window = window
        self._display = window.get_display()
        self._class = css_class
        self._provider = None
        self._monitor = None
        self._pending = 0
        self._watched = None
        self._closed = False
        config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
        self._path = config / "gtk-4.0" / NAME
        window.remove_css_class(css_class)
        if not gtk_supports_blur():
            return
        self._provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            self._display, self._provider, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1
        )
        self._refresh()

    def _watch(self):
        directory = self._path.parent
        while not directory.is_dir() and directory != directory.parent:
            directory = directory.parent
        if self._watched == directory:
            return
        if self._monitor:
            self._monitor.cancel()
        self._monitor = Gio.File.new_for_path(str(directory)).monitor_directory(
            Gio.FileMonitorFlags.WATCH_MOVES, None
        )
        self._monitor.connect("changed", self._changed)
        self._watched = directory

    def _changed(self, monitor, file, other, event):
        if not self._closed and not self._pending:
            self._pending = GLib.idle_add(self._refresh)

    def _refresh(self):
        self._pending = 0
        if self._closed:
            return GLib.SOURCE_REMOVE
        try:
            self._watch()
            content = self._path.read_text()
        except (OSError, UnicodeError, GLib.Error):
            content = ""
        valid = content.startswith(OWNER.decode()) and f"window.{self._class}" in content
        self._window.remove_css_class(self._class)
        self._provider.load_from_string(content if valid else "")
        if valid:
            self._window.add_css_class(self._class)
        return GLib.SOURCE_REMOVE

    def close(self, *, remove_class=True):
        if self._closed:
            return
        self._closed = True
        if self._pending:
            GLib.source_remove(self._pending)
            self._pending = 0
        if self._monitor:
            self._monitor.cancel()
            self._monitor = None
        if self._provider:
            Gtk.StyleContext.remove_provider_for_display(
                self._display, self._provider
            )
            self._provider = None
        if remove_class:
            self._window.remove_css_class(self._class)
        self._window = None
