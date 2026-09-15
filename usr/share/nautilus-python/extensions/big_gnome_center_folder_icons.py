# SPDX-License-Identifier: MIT
"""Open BGC's folder picker without importing application modules into Nautilus."""

import gettext
import logging

import gi

gi.require_version("Nautilus", "4.1")
gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, GObject, Gtk, Nautilus

tr = gettext.translation("big-gnome-center", "/usr/share/locale", fallback=True).gettext
ICON_ATTRIBUTES = ("metadata::custom-icon", "metadata::custom-icon-name")


def icon_metadata(location):
    info = location.query_info(
        ",".join(ICON_ATTRIBUTES), Gio.FileQueryInfoFlags.NONE, None
    )
    return tuple(info.get_attribute_string(key) for key in ICON_ATTRIBUTES)


def refresh_folder_views(location):
    """Reload metadata through Nautilus's native action, only in parent views."""
    parent = location.get_parent()
    application = Gio.Application.get_default()
    if parent is None or not isinstance(application, Gtk.Application):
        return
    try:
        slot_type = GObject.type_from_name("NautilusWindowSlot")
    except RuntimeError:
        return
    pending = list(application.get_windows())
    while pending:
        widget = pending.pop()
        if GObject.type_is_a(widget.__gtype__, slot_type):
            current = widget.get_property("location")
            if current is not None and current.equal(parent):
                widget.activate_action("slot.reload", None)
            continue
        child = widget.get_first_child()
        while child is not None:
            pending.append(child)
            child = child.get_next_sibling()


def position_context_menus(children, position, removed, added):
    """Side anchoring lets GTK slide vertically before considering a resize."""
    for index in range(position, position + added):
        menu = children.get_item(index)
        if isinstance(menu, Gtk.PopoverMenu):
            menu.set_position(Gtk.PositionType.RIGHT)
            menu.set_valign(Gtk.Align.START)


def follow_context_menus():
    """Watch direct file-view children, including concrete Nautilus view subclasses."""
    application = Gio.Application.get_default()
    if not isinstance(application, Gtk.Application):
        return
    try:
        view_type = GObject.type_from_name("NautilusFilesView")
    except RuntimeError:
        return
    pending = list(application.get_windows())
    while pending:
        widget = pending.pop()
        if GObject.type_is_a(widget.__gtype__, view_type):
            if not hasattr(widget, "_bgc_context_children"):
                children = widget.observe_children()
                children.connect("items-changed", position_context_menus)
                widget._bgc_context_children = children
                position_context_menus(children, 0, 0, children.get_n_items())
            continue
        child = widget.get_first_child()
        while child is not None:
            pending.append(child)
            child = child.get_next_sibling()


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
        follow_context_menus()
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
            location = Gio.File.new_for_uri(folder.get_uri())
            before = icon_metadata(location)
            process = Gio.Subprocess.new(
                ["/usr/bin/big-gnome-center-folder-icon", folder.get_uri()],
                Gio.SubprocessFlags.NONE,
            )
            process.wait_async(None, self._finished, (folder, location, before))
        except GLib.Error:
            logging.exception("Cannot launch BGC folder icon picker")

    def _finished(self, process, result, context):
        folder, location, before = context
        try:
            process.wait_finish(result)
            if not folder.is_gone():
                folder.invalidate_extension_info()
                if icon_metadata(location) != before:
                    refresh_folder_views(location)
        except GLib.Error:
            logging.exception("BGC folder icon picker failed")
