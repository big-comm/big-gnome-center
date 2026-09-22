# SPDX-License-Identifier: MIT
"""Open BGC's folder picker without importing application modules into Nautilus."""

import gettext
import logging

import gi

gi.require_version("Nautilus", "4.1")
gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, GObject, Gtk, Nautilus

tr = gettext.translation("big-gnome-center", "/usr/share/locale", fallback=True).gettext


def reload_active_view():
    """Ask Nautilus to reload the current slot without inspecting its widgets."""
    application = Gio.Application.get_default()
    if not isinstance(application, Gtk.Application):
        return
    window = application.get_active_window()
    if window is not None:
        window.activate_action("slot.reload", None)


class BigGnomeCenterFolderIcons(GObject.GObject, Nautilus.MenuProvider):
    def get_file_items(self, files):
        if len(files) != 1:
            return []
        return self._items(files[0], "Selection")

    def get_background_items(self, folder):
        return self._items(folder, "Background")

    def _items(self, folder, context):
        if folder.is_gone() or not folder.is_directory() or folder.get_uri_scheme() != "file":
            return []
        item = Nautilus.MenuItem(
            name=f"BigGnomeCenter::FolderIcon{context}",
            label=tr("Customize Folder Icon…"),
            tip=tr("Choose a folder design that follows the theme color"),
            icon="folder-symbolic",
        )
        item.connect("activate", self._activate, folder)
        return [item]

    def _activate(self, item, folder):
        if folder.is_gone():
            return
        try:
            process = Gio.Subprocess.new(
                ["/usr/bin/big-gnome-center-folder-icon", folder.get_uri()],
                Gio.SubprocessFlags.NONE,
            )
            process.wait_async(None, self._finished, folder)
        except GLib.Error:
            logging.exception("Cannot launch BGC folder icon picker")

    def _finished(self, process, result, folder):
        try:
            process.wait_finish(result)
            if not folder.is_gone():
                folder.invalidate_extension_info()
                reload_active_view()
        except GLib.Error:
            logging.exception("BGC folder icon picker failed")
