# SPDX-License-Identifier: MIT
"""Opt-in cursor matching, independent of the settings window lifetime."""

import json
import logging
import re
import subprocess
import sys
from pathlib import Path

from gi.repository import Gio, GLib

from constants import ACCENT_COLORS, tr
from material_color_match import find_closest_theme

SCHEMA = "org.communitybig.big-gnome-center.themes"
KEY = "cursor-follow-accent"
PREFIX = "Bibata-Material-"
PALETTES = Path("/usr/share/big-bibata-cursor-theme/material-palettes.json")
log = logging.getLogger(__name__)
_ACCENT_FAMILIES = {
    "blue": {"Ice-Blue", "Sky-Blue", "Deep-Blue", "Soft-Blue"},
    "teal": {"Teal", "Seafoam", "Deep-Blue"},
    "green": {"Sage", "Lime", "Moss", "Midnight"},
    "yellow": {"Sand", "Beige"},
    "orange": {"Peach", "Apricot", "Sunset"},
    "red": {"Blush", "Salmon"},
    "pink": {"Pink-Pastel", "Pink-Rose"},
    "purple": {"Lilac", "Violet"},
    "slate": {"Cloud", "Grey", "Slate", "Charcoal"},
    "maia": {"Mint", "Seafoam", "Teal"},
}


def preferences():
    source = Gio.SettingsSchemaSource.get_default()
    schema = source.lookup(SCHEMA, True) if source else None
    return Gio.Settings.new_full(schema, None, None) if schema else None


def is_enabled():
    settings = preferences()
    return bool(settings and settings.get_boolean(KEY))


def read_palettes():
    try:
        data = json.loads(PALETTES.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def matching_theme(accent, scheme, installed, palettes):
    light = scheme != "prefer-dark"
    candidates = {}
    for name, colors in palettes.items():
        if (not re.fullmatch(r"[A-Za-z0-9-]+", name) or name == "Classic"
                or name.endswith("-Light") != light or PREFIX + name not in installed
                or not isinstance(colors, dict)):
            continue
        if all(re.fullmatch(r"#[0-9a-fA-F]{6}", str(colors.get(key, "")))
               for key in ("body", "primary")):
            candidates[name] = colors
    if not candidates:
        return ""
    # Avoid a neutral palette winning solely through similar luminance.
    family = _ACCENT_FAMILIES.get(accent, _ACCENT_FAMILIES["blue"])
    matching_family = {name: colors for name, colors in candidates.items()
                       if name.removesuffix("-Light") in family}
    candidates = matching_family or candidates
    name, _score = find_closest_theme(ACCENT_COLORS.get(accent, ACCENT_COLORS["blue"]),
                                    candidates)
    return PREFIX + name


def installed_themes():
    from theme_manager import ThemeMgr

    return ThemeMgr.list_themes("cursors")


def set_enabled(enabled):
    settings = preferences()
    if settings is None:
        return False, "Cursor preferences schema is unavailable"
    if not settings.is_writable(KEY):
        return False, "Cursor preferences are locked"
    if not enabled:
        return settings.set_boolean(KEY, False), ""
    interface = Gio.Settings.new("org.gnome.desktop.interface")
    target = matching_theme(interface.get_string("accent-color"),
                            interface.get_string("color-scheme"),
                            installed_themes(), read_palettes())
    if not target:
        return False, tr("Install big-bibata-cursor-theme to use matching cursors.")
    if not interface.is_writable("cursor-theme"):
        return False, "Cursor theme is locked"
    previous = interface.get_string("cursor-theme")
    if not settings.set_boolean(KEY, True):
        return False, "Cannot save cursor preferences"
    if not interface.set_string("cursor-theme", target):
        settings.set_boolean(KEY, False)
        return False, "Cannot apply cursor theme"
    Gio.Settings.sync()
    try:
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--watch"],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as error:
        settings.set_boolean(KEY, False)
        interface.set_string("cursor-theme", previous)
        return False, str(error)
    return True, ""


class CursorAccentFollower:
    def __init__(self, interface, settings, stopped, *,
                 palette_loader=read_palettes, theme_loader=installed_themes):
        self.interface = interface
        self.settings = settings
        self.stopped = stopped
        self.palette_loader = palette_loader
        self.theme_loader = theme_loader
        self._signals = []
        self._pending = 0
        self._writing = False
        self._expected = ""

    def start(self):
        for key in ("accent-color", "color-scheme"):
            self._signals.append((self.interface, self.interface.connect(
                f"changed::{key}", lambda *_args: self.queue())))
        self._signals.append((self.interface, self.interface.connect(
            "changed::cursor-theme", self._cursor_changed)))
        self._signals.append((self.settings, self.settings.connect(
            f"changed::{KEY}", self._preference_changed)))
        self.queue()

    def _preference_changed(self, *_args):
        if self.settings.get_boolean(KEY):
            self.queue()
        else:
            self.stopped()

    def _cursor_changed(self, *_args):
        current = self.interface.get_string("cursor-theme")
        if not self._writing and current != self._expected:
            # A manual selection takes precedence, including other settings apps.
            self.settings.set_boolean(KEY, False)

    def queue(self):
        if not self._pending:
            self._pending = GLib.timeout_add(100, self.sync)

    def sync(self):
        self._pending = 0
        if not self.settings.get_boolean(KEY):
            return GLib.SOURCE_REMOVE
        target = matching_theme(self.interface.get_string("accent-color"),
                                self.interface.get_string("color-scheme"),
                                self.theme_loader(), self.palette_loader())
        if not target or not self.interface.is_writable("cursor-theme"):
            return GLib.SOURCE_REMOVE
        self._expected = target
        if self.interface.get_string("cursor-theme") != target:
            self._writing = True
            try:
                if not self.interface.set_string("cursor-theme", target):
                    log.warning("Cannot apply matching cursor %s", target)
            finally:
                self._writing = False
        return GLib.SOURCE_REMOVE

    def stop(self):
        if self._pending:
            GLib.source_remove(self._pending)
            self._pending = 0
        for settings, signal in self._signals:
            settings.disconnect(signal)
        self._signals.clear()


def main():
    # One watcher per user; another activation reuses the running instance.
    app = Gio.Application(application_id="br.com.biglinux.BigGnomeCenter.CursorAccent")
    follower = None

    def activate(application):
        nonlocal follower
        if follower is not None:
            return
        settings = preferences()
        if settings is None or not settings.get_boolean(KEY):
            return
        interface = Gio.Settings.new("org.gnome.desktop.interface")
        follower = CursorAccentFollower(interface, settings, application.quit)
        application.hold()
        follower.start()

    app.connect("activate", activate)
    try:
        return app.run([sys.argv[0]])
    finally:
        if follower is not None:
            follower.stop()


if __name__ == "__main__":
    raise SystemExit(main())
