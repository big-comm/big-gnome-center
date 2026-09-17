# SPDX-License-Identifier: MIT
"""Exercise opt-in matching and manual override precedence."""

from unittest.mock import Mock

import pytest

import cursor_accent as ca
from material_color_match import delta_e_hex

PALETTES = {
    "Blue": {"body": "#153050", "primary": "#3584e4"},
    "Red": {"body": "#501530", "primary": "#e62d42"},
    "Blue-Light": {"body": "#eeeeff", "primary": "#3584e4"},
    "Red-Light": {"body": "#ffeeee", "primary": "#e62d42"},
}
INSTALLED = [ca.PREFIX + name for name in PALETTES]


class Settings:
    def __init__(self, **values):
        self.values = values
        self.signals = {}
        self.writes = []
        self.locked = set()
        self.next_id = 0

    def connect(self, signal, callback):
        self.next_id += 1
        self.signals[self.next_id] = (signal, callback)
        return self.next_id

    def disconnect(self, signal):
        del self.signals[signal]

    def get_string(self, key):
        return self.values[key]

    get_boolean = get_string

    def is_writable(self, key):
        return key not in self.locked

    def set_string(self, key, value):
        if not self.is_writable(key):
            return False
        if self.values.get(key) != value:
            self.values[key] = value
            self.writes.append((key, value))
            for signal, callback in list(self.signals.values()):
                if signal == f"changed::{key}":
                    callback(self, key)
        return True

    set_boolean = set_string


def test_matching_respects_scheme_and_installed_themes():
    assert ca.matching_theme("blue", "prefer-dark", INSTALLED, PALETTES) == ca.PREFIX + "Blue"
    assert ca.matching_theme("red", "prefer-light", INSTALLED, PALETTES) == ca.PREFIX + "Red-Light"
    assert ca.matching_theme("blue", "default", INSTALLED, PALETTES).endswith("-Light")
    assert not ca.matching_theme("blue", "prefer-dark", [], PALETTES)
    assert not ca.matching_theme("blue", "prefer-dark", INSTALLED, {"Blue": {"body": "oops"}})


def test_color_distance_identity_and_symmetry():
    assert delta_e_hex("#3584e4", "#3584e4") == pytest.approx(0)
    forward = delta_e_hex("#3584e4", "#ed5b00")
    assert forward > 0
    assert forward == pytest.approx(delta_e_hex("#ed5b00", "#3584e4"))


def test_accent_family_prevents_neutral_blue_and_purple_matches():
    palettes = {
        "Sky-Blue": {"body": "#0e3251", "primary": "#8dcdff"},
        "Charcoal": {"body": "#0f1519", "primary": "#7591a3"},
        "Violet": {"body": "#402848", "primary": "#edb8ff"},
        "Slate": {"body": "#1f262b", "primary": "#8292a2"},
    }
    installed = [ca.PREFIX + name for name in palettes]
    assert ca.matching_theme("blue", "prefer-dark", installed, palettes) == ca.PREFIX + "Sky-Blue"
    assert ca.matching_theme("purple", "prefer-dark", installed, palettes) == ca.PREFIX + "Violet"


@pytest.fixture
def follower():
    interface = Settings(**{"accent-color": "blue", "color-scheme": "prefer-dark",
                            "cursor-theme": "Bibata-Modern-Classic"})
    prefs = Settings(**{ca.KEY: True})
    stopped = Mock()
    follower = ca.CursorAccentFollower(interface, prefs, stopped,
                                      palette_loader=lambda: PALETTES,
                                      theme_loader=lambda: INSTALLED)
    follower.start()
    yield follower, interface, prefs, stopped
    follower.stop()


def flush(follower):
    if follower._pending:
        ca.GLib.source_remove(follower._pending)
    follower.sync()


def test_follower_updates_accent_and_appearance(follower):
    watcher, interface, prefs, stopped = follower
    flush(watcher)
    assert interface.get_string("cursor-theme") == ca.PREFIX + "Blue"
    interface.set_string("accent-color", "red")
    interface.set_string("color-scheme", "prefer-light")
    flush(watcher)
    assert interface.get_string("cursor-theme") == ca.PREFIX + "Red-Light"
    assert prefs.get_boolean(ca.KEY)
    stopped.assert_not_called()


def test_manual_selection_disables_pending_matching(follower):
    watcher, interface, prefs, stopped = follower
    flush(watcher)
    interface.set_string("accent-color", "red")
    interface.set_string("cursor-theme", "Adwaita")
    assert not prefs.get_boolean(ca.KEY)
    stopped.assert_called_once()
    flush(watcher)
    assert interface.get_string("cursor-theme") == "Adwaita"


def test_disabled_missing_and_locked_themes_are_untouched(follower):
    watcher, interface, prefs, _stopped = follower
    prefs.set_boolean(ca.KEY, False)
    flush(watcher)
    assert not interface.writes
    prefs.set_boolean(ca.KEY, True)
    watcher.theme_loader = lambda: []
    flush(watcher)
    assert not interface.writes
    watcher.theme_loader = lambda: INSTALLED
    interface.locked.add("cursor-theme")
    flush(watcher)
    assert not interface.writes


def test_stop_disconnects_signals_and_cancels_pending_work(follower):
    watcher, interface, prefs, _stopped = follower
    watcher.stop()
    assert not watcher._pending
    assert not interface.signals
    assert not prefs.signals


def test_enable_with_missing_package_preserves_preference(monkeypatch):
    prefs = Settings(**{ca.KEY: False})
    interface = Settings(**{"accent-color": "blue", "color-scheme": "prefer-dark"})
    monkeypatch.setattr(ca, "preferences", lambda: prefs)
    monkeypatch.setattr(ca.Gio.Settings, "new", lambda _schema: interface)
    monkeypatch.setattr(ca, "read_palettes", lambda: {})
    monkeypatch.setattr(ca, "installed_themes", lambda: INSTALLED)
    ok, error = ca.set_enabled(True)
    assert not ok and "big-bibata-cursor-theme" in error
    assert not prefs.get_boolean(ca.KEY)
