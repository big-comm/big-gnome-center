# SPDX-License-Identifier: MIT
"""
ui/page_behavior.py - GNOME behavior settings that GNOME Settings does not show.

Every control is bound live to the user's GSettings: no apply button, and a
change made elsewhere (GNOME Settings, gsettings) shows here at once.

DEVELOPER NOTE - DO NOT name any variable `_` in this file.
"""

from typing import Callable, List, Optional, Tuple

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk

from constants import tr

INTERFACE_SCHEMA = "org.gnome.desktop.interface"
WM_SCHEMA = "org.gnome.desktop.wm.preferences"
MUTTER_SCHEMA = "org.gnome.mutter"
PRIMARY_PASTE_KEY = "gtk-enable-primary-paste"


def schema_settings(schema_id: str, key: str) -> Optional[Gio.Settings]:
    """The settings for `schema_id`, or None where the schema lacks `key`."""
    source = Gio.SettingsSchemaSource.get_default()
    schema = source.lookup(schema_id, True) if source else None
    if schema is None or not schema.has_key(key):
        return None
    return Gio.Settings.new(schema_id)


def titlebar_actions() -> List[Tuple[str, str]]:
    # Shading does nothing on Wayland, so it is not offered.
    return [
        ("toggle-maximize", tr("Maximize")),
        ("toggle-maximize-horizontally", tr("Maximize width")),
        ("toggle-maximize-vertically", tr("Maximize height")),
        ("minimize", tr("Minimize")),
        ("lower", tr("Send to back")),
        ("menu", tr("Show window menu")),
        ("none", tr("Do nothing")),
    ]


def move_modifiers() -> List[Tuple[str, str]]:
    return [
        ("<Super>", tr("Super")),
        ("<Alt>", tr("Alt")),
        ("", tr("Disabled")),
    ]


class BehaviorPage(Gtk.Box):
    """Desktop behavior switches, bound live to the user's GSettings."""

    def __init__(
        self,
        pool,
        toast_cb,
        settings_for: Optional[Callable[[str, str], Optional[Gio.Settings]]] = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._pool = pool
        self._toast = toast_cb
        self._settings_for = settings_for or schema_settings
        self._settings = {}
        self.rows = {}
        self._build()

    # -- Settings ------------------------------------------------------------

    def _get_settings(self, schema_id: str, key: str) -> Optional[Gio.Settings]:
        if schema_id not in self._settings:
            self._settings[schema_id] = self._settings_for(schema_id, key)
        settings = self._settings[schema_id]
        if settings is None or not settings.props.settings_schema.has_key(key):
            return None
        return settings

    # -- UI root -------------------------------------------------------------

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
        outer.append(self._build_windows_group())
        outer.append(self._build_titlebar_group())

        clamp.set_child(outer)
        sc.set_child(clamp)
        self.append(sc)

    def _build_pointer_group(self) -> Adw.PreferencesGroup:
        grp = Adw.PreferencesGroup()
        grp.set_title(tr("Mouse and touchpad"))
        # GNOME 51 turned this off by default; Big Gnome Center ships it on.
        grp.add(
            self._switch_row(
                "primary-paste",
                INTERFACE_SCHEMA,
                PRIMARY_PASTE_KEY,
                tr("Middle-click paste"),
                tr("Paste the selected text with the middle mouse button or a three-finger tap"),
            )
        )
        grp.add(self._focus_row())
        return grp

    def _build_windows_group(self) -> Adw.PreferencesGroup:
        grp = Adw.PreferencesGroup()
        grp.set_title(tr("Windows"))
        grp.add(
            self._switch_row(
                "attach-dialogs",
                MUTTER_SCHEMA,
                "attach-modal-dialogs",
                tr("Attach dialogs to their window"),
                tr("Dialogs stay over the window that opened them and move with it"),
            )
        )
        grp.add(
            self._choice_row(
                "move-modifier",
                WM_SCHEMA,
                "mouse-button-modifier",
                tr("Key to move windows"),
                tr("Hold it and drag any part of a window to move it"),
                move_modifiers(),
            )
        )
        grp.add(
            self._switch_row(
                "resize-right-button",
                WM_SCHEMA,
                "resize-with-right-button",
                tr("Resize with the right button"),
                tr("With that key held, drag with the right button to resize"),
            )
        )
        return grp

    def _build_titlebar_group(self) -> Adw.PreferencesGroup:
        grp = Adw.PreferencesGroup()
        grp.set_title(tr("Title bar"))
        for name, key, title in (
            ("double-click", "action-double-click-titlebar", tr("Double-click")),
            ("middle-click", "action-middle-click-titlebar", tr("Middle-click")),
            ("right-click", "action-right-click-titlebar", tr("Right-click")),
        ):
            grp.add(self._choice_row(name, WM_SCHEMA, key, title, None, titlebar_actions()))
        return grp

    # -- Rows ----------------------------------------------------------------

    def _switch_row(self, name, schema_id, key, title, subtitle) -> Adw.SwitchRow:
        row = Adw.SwitchRow()
        row.set_title(title)
        row.set_subtitle(subtitle)
        settings = self._get_settings(schema_id, key)
        if settings is not None:
            settings.bind(key, row, "active", Gio.SettingsBindFlags.DEFAULT)
        else:
            row.set_sensitive(False)
        self.rows[name] = row
        return row

    def _focus_row(self) -> Adw.SwitchRow:
        """'sloppy' focus as a switch; GNOME Settings writes the same key."""
        row = Adw.SwitchRow()
        row.set_title(tr("Activate windows on hover"))
        row.set_subtitle(tr("Focus the window under the pointer without clicking"))
        self.rows["focus-hover"] = row
        settings = self._get_settings(WM_SCHEMA, "focus-mode")
        if settings is None:
            row.set_sensitive(False)
            return row

        def follow(*_args) -> None:
            hover = settings.get_string("focus-mode") != "click"
            if row.get_active() != hover:
                row.set_active(hover)

        def write(*_args) -> None:
            current = settings.get_string("focus-mode")
            if row.get_active() and current == "click":
                settings.set_string("focus-mode", "sloppy")
            elif not row.get_active() and current != "click":
                settings.set_string("focus-mode", "click")

        follow()
        row.connect("notify::active", write)
        settings.connect("changed::focus-mode", follow)
        return row

    def _choice_row(self, name, schema_id, key, title, subtitle, choices) -> Adw.ComboRow:
        row = Adw.ComboRow()
        row.set_title(title)
        if subtitle:
            row.set_subtitle(subtitle)
        self.rows[name] = row
        settings = self._get_settings(schema_id, key)
        values = [value for value, _label in choices]
        model = Gtk.StringList.new([label for _value, label in choices])
        row.set_model(model)
        if settings is None:
            row.set_sensitive(False)
            return row

        def follow(*_args) -> None:
            current = settings.get_string(key)
            if current not in values:
                # A value set elsewhere stays visible instead of being replaced.
                values.append(current)
                model.append(current)
            index = values.index(current)
            if row.get_selected() != index:
                row.set_selected(index)

        def write(*_args) -> None:
            index = row.get_selected()
            if 0 <= index < len(values) and settings.get_string(key) != values[index]:
                settings.set_string(key, values[index])

        follow()
        row.connect("notify::selected", write)
        settings.connect(f"changed::{key}", follow)
        return row
