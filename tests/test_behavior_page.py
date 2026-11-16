# SPDX-License-Identifier: MIT
"""Middle-click paste: shipped on by default and switchable in Behavior."""

import shutil
import subprocess
from pathlib import Path

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, Gtk

from ui.page_behavior import BehaviorPage, INTERFACE_SCHEMA, PRIMARY_PASTE_KEY

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


def test_switch_follows_and_writes_the_user_setting():
    if not Gtk.init_check() or Gdk.Display.get_default() is None:
        pytest.skip("Requires a GTK display")
    Adw.init()
    if Gio.SettingsSchemaSource.get_default().lookup(INTERFACE_SCHEMA, True) is None:
        pytest.skip("Requires the GNOME interface schema")
    settings = Gio.Settings.new_with_backend(
        INTERFACE_SCHEMA, Gio.memory_settings_backend_new()
    )
    settings.set_boolean(PRIMARY_PASTE_KEY, True)
    page = BehaviorPage(None, None, settings=settings)
    row = page.primary_paste_row
    assert row.get_active()
    row.set_active(False)
    assert settings.get_boolean(PRIMARY_PASTE_KEY) is False
    settings.set_boolean(PRIMARY_PASTE_KEY, True)
    assert row.get_active()


def test_behavior_page_is_in_the_sidebar():
    window = (ROOT / "usr/share/big-gnome-center/ui/window.py").read_text()
    assert '("behavior", tr("Behavior"), "preferences-system-symbolic")' in window
    assert '"behavior": lambda: BehaviorPage(self._pool, self._toast)' in window
