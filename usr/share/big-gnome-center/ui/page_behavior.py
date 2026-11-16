# SPDX-License-Identifier: MIT
"""
ui/page_behavior.py - GNOME behavior settings that GNOME Settings does not show.

DEVELOPER NOTE - DO NOT name any variable `_` in this file.
"""

from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk

from constants import tr

INTERFACE_SCHEMA = "org.gnome.desktop.interface"
PRIMARY_PASTE_KEY = "gtk-enable-primary-paste"


def _interface_settings() -> Optional[Gio.Settings]:
    source = Gio.SettingsSchemaSource.get_default()
    schema = source.lookup(INTERFACE_SCHEMA, True) if source else None
    if schema is None or not schema.has_key(PRIMARY_PASTE_KEY):
        return None
    return Gio.Settings.new(INTERFACE_SCHEMA)


class BehaviorPage(Gtk.Box):
    """Desktop behavior switches, bound live to the user's GSettings."""

    def __init__(self, pool, toast_cb, settings: Optional[Gio.Settings] = None) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._pool = pool
        self._toast = toast_cb
        self._settings = settings if settings is not None else _interface_settings()
        self.primary_paste_row: Optional[Adw.SwitchRow] = None
        self._build()

    def _build(self) -> None:
        sc = Gtk.ScrolledWindow()
        sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sc.set_vexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(820)
        clamp.set_tightening_threshold(600)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22)
        outer.set_margin_start(22)
        outer.set_margin_end(22)
        outer.set_margin_top(8)
        outer.set_margin_bottom(24)
        outer.append(self._build_pointer_group())

        clamp.set_child(outer)
        sc.set_child(clamp)
        self.append(sc)

    def _build_pointer_group(self) -> Adw.PreferencesGroup:
        grp = Adw.PreferencesGroup()
        grp.set_title(tr("Mouse and touchpad"))

        row = Adw.SwitchRow()
        row.set_title(tr("Middle-click paste"))
        row.set_subtitle(tr(
            "Paste the selected text with the middle mouse button "
            "or a three-finger tap"
        ))
        # GNOME 51 turned this off by default; Big Gnome Center ships it on.
        if self._settings is not None:
            self._settings.bind(
                PRIMARY_PASTE_KEY, row, "active", Gio.SettingsBindFlags.DEFAULT
            )
        else:
            row.set_sensitive(False)
        grp.add(row)
        self.primary_paste_row = row
        return grp
