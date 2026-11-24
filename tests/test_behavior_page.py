# SPDX-License-Identifier: MIT
"""Behavior page: middle-click paste on by default, every switch bound live."""

import shutil
import subprocess
from pathlib import Path

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, Gtk

from ui.page_behavior import (
    INTERFACE_SCHEMA,
    MUTTER_SCHEMA,
    PRIMARY_PASTE_KEY,
    WM_SCHEMA,
    BehaviorPage,
    move_modifiers,
    titlebar_actions,
)

ROOT = Path(__file__).resolve().parents[1]
OVERRIDE = ROOT / "usr/share/glib-2.0/schemas/50_big-gnome-center.gschema.override"
SYSTEM_SCHEMAS = Path("/usr/share/glib-2.0/schemas")


def test_override_turns_middle_click_paste_back_on(tmp_path):
    schema = SYSTEM_SCHEMAS / f"{INTERFACE_SCHEMA}.gschema.xml"
    if not schema.exists() or shutil.which("glib-compile-schemas") is None:
        pytest.skip("Requires the installed GNOME interface schema")
    for source in SYSTEM_SCHEMAS.glob("org.gnome.desktop.*.xml"):
        shutil.copy(source, tmp_path)
    shutil.copy(OVERRIDE, tmp_path)
    subprocess.run(["glib-compile-schemas", "--strict", str(tmp_path)], check=True)
    source = Gio.SettingsSchemaSource.new_from_directory(str(tmp_path), None, True)
    key = source.lookup(INTERFACE_SCHEMA, False).get_key(PRIMARY_PASTE_KEY)
    assert key.get_default_value().unpack() is True


@pytest.fixture
def page():
    if not Gtk.init_check() or Gdk.Display.get_default() is None:
        pytest.skip("Requires a GTK display")
    Adw.init()
    source = Gio.SettingsSchemaSource.get_default()
    if any(source.lookup(s, True) is None for s in (INTERFACE_SCHEMA, WM_SCHEMA, MUTTER_SCHEMA)):
        pytest.skip("Requires the GNOME and Mutter schemas")
    backend = Gio.memory_settings_backend_new()
    stores = {}

    def settings_for(schema_id, _key):
        stores.setdefault(schema_id, Gio.Settings.new_with_backend(schema_id, backend))
        return stores[schema_id]

    built = BehaviorPage(None, None, settings_for=settings_for)
    built.stores = stores
    return built


@pytest.mark.parametrize(
    "name, schema_id, key",
    [
        ("primary-paste", INTERFACE_SCHEMA, PRIMARY_PASTE_KEY),
        ("attach-dialogs", MUTTER_SCHEMA, "attach-modal-dialogs"),
        ("resize-right-button", WM_SCHEMA, "resize-with-right-button"),
    ],
)
def test_switches_write_and_follow_their_key(page, name, schema_id, key):
    row, settings = page.rows[name], page.stores[schema_id]
    assert row.get_active() == settings.get_boolean(key)
    row.set_active(not row.get_active())
    assert settings.get_boolean(key) == row.get_active()
    settings.set_boolean(key, not row.get_active())
    assert row.get_active() == settings.get_boolean(key)


def test_hover_focus_maps_to_sloppy_and_back_to_click(page):
    row, settings = page.rows["focus-hover"], page.stores[WM_SCHEMA]
    assert settings.get_string("focus-mode") == "click" and not row.get_active()
    row.set_active(True)
    assert settings.get_string("focus-mode") == "sloppy"
    settings.set_string("focus-mode", "mouse")  # set in GNOME Settings
    assert row.get_active()
    assert settings.get_string("focus-mode") == "mouse", "kept as chosen elsewhere"
    row.set_active(False)
    assert settings.get_string("focus-mode") == "click"


@pytest.mark.parametrize(
    "name, key, choices",
    [
        ("double-click", "action-double-click-titlebar", titlebar_actions()),
        ("middle-click", "action-middle-click-titlebar", titlebar_actions()),
        ("right-click", "action-right-click-titlebar", titlebar_actions()),
        ("move-modifier", "mouse-button-modifier", move_modifiers()),
    ],
)
def test_choices_write_and_follow_their_key(page, name, key, choices):
    row, settings = page.rows[name], page.stores[WM_SCHEMA]
    values = [value for value, _label in choices]
    assert values[row.get_selected()] == settings.get_string(key)
    for index, value in enumerate(values):
        row.set_selected(index)
        assert settings.get_string(key) == value
    settings.set_string(key, values[0])
    assert row.get_selected() == 0


def test_a_value_set_elsewhere_is_shown_not_replaced(page):
    row, settings = page.rows["move-modifier"], page.stores[WM_SCHEMA]
    settings.set_string("mouse-button-modifier", "<Control>")
    assert row.get_model().get_string(row.get_selected()) == "<Control>"
    assert settings.get_string("mouse-button-modifier") == "<Control>"


def test_missing_schema_disables_its_rows():
    if not Gtk.init_check() or Gdk.Display.get_default() is None:
        pytest.skip("Requires a GTK display")
    Adw.init()
    built = BehaviorPage(None, None, settings_for=lambda _schema, _key: None)
    assert built.rows and not any(row.get_sensitive() for row in built.rows.values())


def test_behavior_page_is_in_the_sidebar():
    window = (ROOT / "usr/share/big-gnome-center/ui/window.py").read_text()
    assert '("behavior", tr("Behavior"), "preferences-system-symbolic")' in window
    assert '"behavior": lambda: BehaviorPage(self._pool, self._toast)' in window
