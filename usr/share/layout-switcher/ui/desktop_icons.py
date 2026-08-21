# SPDX-License-Identifier: MIT
"""Global GTK4-DING controls shared by every layout."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from constants import tr
from extension_manager import ExtMgr

GTK4_DING_UUID = "gtk4-ding@smedius.gitlab.com"


class DesktopIconsControls(Gtk.Box):
    """Toggle GTK4-DING for the active layout."""

    def __init__(self, pool, toast_cb) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._pool = pool
        self._toast = toast_cb
        self._syncing = False

        group = Adw.PreferencesGroup(title=tr("Desktop"))
        self._row = Adw.ActionRow(
            title=tr("Desktop icons"),
            subtitle=tr("Show files and folders on the desktop"),
        )

        settings_button = Gtk.Button.new_from_icon_name("emblem-system-symbolic")
        settings_button.add_css_class("flat")
        settings_button.set_valign(Gtk.Align.CENTER)
        settings_button.set_tooltip_text(tr("Desktop icon settings"))
        settings_button.connect(
            "clicked",
            lambda button: ExtMgr.open_prefs(GTK4_DING_UUID),
        )
        self._settings_button = settings_button
        self._row.add_suffix(settings_button)

        self._switch = Gtk.Switch()
        self._switch.set_valign(Gtk.Align.CENTER)
        self._switch.update_property(
            [Gtk.AccessibleProperty.LABEL],
            [tr("Desktop icons")],
        )
        self._switch.connect("notify::active", self._on_toggled)
        self._row.add_suffix(self._switch)
        self._row.set_activatable_widget(self._switch)

        group.add(self._row)
        self.append(group)
        self.refresh()

    def refresh(self) -> None:
        """Synchronize the row with the extension's current global state."""
        installed = ExtMgr.is_installed(GTK4_DING_UUID)
        active = ExtMgr.is_enabled(GTK4_DING_UUID) if installed else False

        self._syncing = True
        self._switch.set_active(active)
        self._syncing = False
        self._switch.set_sensitive(installed)
        self._settings_button.set_sensitive(installed)
        self._row.set_subtitle(
            tr("Show files and folders on the desktop")
            if installed
            else tr("GTK4 Desktop Icons NG is not installed")
        )

    def _on_toggled(self, switch: Gtk.Switch, param) -> None:
        if self._syncing:
            return

        enable = switch.get_active()
        switch.set_sensitive(False)

        def task() -> None:
            ok, message = ExtMgr.set_enabled(GTK4_DING_UUID, enable)
            GLib.idle_add(self._finish_toggle, ok, message, enable)

        self._pool.submit(task)

    def _finish_toggle(self, ok: bool, message: str, enable: bool) -> bool:
        if ok:
            self.refresh()
            self._toast(tr("Desktop icons enabled") if enable else tr("Desktop icons disabled"))
        else:
            self.refresh()
            self._toast(
                tr("Could not change desktop icons: {message}").format(
                    message=message,
                )
            )
        return GLib.SOURCE_REMOVE
