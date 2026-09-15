#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Folder icon picker launched by the Nautilus menu provider."""

import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk, Pango

from constants import APP_ID, tr
from folder_icons import ATTRIBUTES, available_icons, read_metadata, save_icon, selected_icon


class FolderIconWindow(Adw.ApplicationWindow):
    def __init__(self, app, folder):
        super().__init__(
            application=app, title=tr("Folder Icon"), default_width=660, default_height=620
        )
        self.folder = folder
        self._busy = False
        self._selected = None
        self._metadata = dict.fromkeys(ATTRIBUTES)
        self._ready = False
        self._theme = Gtk.Settings.get_default()
        self._theme_signal = self._theme.connect("notify::gtk-icon-theme-name", self._reload)
        self.connect("close-request", self._close_requested)
        self.connect("destroy", self._destroyed)

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for side in ("top", "bottom", "start", "end"):
            getattr(body, f"set_margin_{side}")(18)
        toolbar.set_content(body)
        self.set_content(toolbar)
        title = Gtk.Label(
            label=folder.get_basename(),
            xalign=0,
            ellipsize=Pango.EllipsizeMode.MIDDLE,
            tooltip_text=folder.get_parse_name(),
            css_classes=["title-2"],
        )
        body.append(title)
        self.description = Gtk.Label(
            label=tr("Choose a design. The folder color follows your system theme."),
            xalign=0,
            wrap=True,
            css_classes=["dim-label"],
        )
        body.append(self.description)
        self.search = Gtk.SearchEntry(placeholder_text=tr("Search folder icons"))
        self.search.connect("search-changed", self._search_changed)
        body.append(self.search)
        self.grid = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.SINGLE,
            activate_on_single_click=True,
            homogeneous=True,
            row_spacing=8,
            column_spacing=8,
            min_children_per_line=2,
            max_children_per_line=5,
            valign=Gtk.Align.START,
        )
        self.grid.set_filter_func(self._matches)
        self.grid.connect("selected-children-changed", self._selection_changed)
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroll.set_child(self.grid)
        body.append(scroll)
        self.message = Gtk.Label(xalign=0, wrap=True, visible=False)
        body.append(self.message)
        actions = Gtk.Box(spacing=8)
        self.restore = Gtk.Button(label=tr("Restore Default"))
        self.restore.connect("clicked", lambda button: self._save(None))
        actions.append(self.restore)
        actions.append(Gtk.Box(hexpand=True))
        self.cancel = Gtk.Button(label=tr("Cancel"))
        self.cancel.connect("clicked", lambda button: self.close())
        actions.append(self.cancel)
        self.apply = Gtk.Button(label=tr("Apply"), css_classes=["suggested-action"])
        self.apply.connect("clicked", lambda button: self._save(self._selected))
        actions.append(self.apply)
        body.append(actions)
        try:
            self._metadata = read_metadata(folder)
            self._ready = True
        except Exception as error:
            self._show_message(str(error), error=True)
        self._reload()

    def _reload(self, *args):
        self.choices = available_icons(self._theme.get_property("gtk-icon-theme-name"))
        wanted = self._selected or selected_icon(self._metadata, self.choices)
        self._selected = None
        while child := self.grid.get_first_child():
            self.grid.remove(child)
        target = None
        for icon in self.choices:
            tile = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=6,
                margin_top=8,
                margin_bottom=8,
                margin_start=4,
                margin_end=4,
            )
            tile.append(Gtk.Image(icon_name=icon.name, pixel_size=64))
            tile.append(
                Gtk.Label(
                    label=icon.label,
                    ellipsize=Pango.EllipsizeMode.END,
                    wrap=True,
                    wrap_mode=Pango.WrapMode.WORD_CHAR,
                    lines=2,
                    max_width_chars=13,
                    justify=Gtk.Justification.CENTER,
                    tooltip_text=icon.label,
                )
            )
            child = Gtk.FlowBoxChild(child=tile)
            child.icon_name = icon.name
            child.search_text = (icon.label + " " + " ".join(icon.aliases)).casefold()
            child.update_property([Gtk.AccessibleProperty.LABEL], [icon.label])
            self.grid.append(child)
            if icon.name == wanted:
                target = child
        if target:
            self.grid.select_child(target)
        else:
            self.grid.unselect_all()
        self._update_actions()
        if not self._ready:
            return
        if not self.choices:
            self._show_message(tr("Select the BigIcons Papient icon theme to choose a design."))
        elif any(self._metadata.values()) and not selected_icon(self._metadata, self.choices):
            self._show_message(
                tr("Your custom image is kept until you apply a design or restore the default.")
            )
        else:
            self.message.set_visible(False)

    def _matches(self, child):
        return self.search.get_text().strip().casefold() in child.search_text

    def _search_changed(self, entry):
        self.grid.invalidate_filter()
        for child in self.grid.get_selected_children():
            if not self._matches(child):
                self.grid.unselect_child(child)

    def _selection_changed(self, grid):
        children = grid.get_selected_children()
        self._selected = children[0].icon_name if children else None
        if hasattr(self, "apply"):
            self._update_actions()

    def _update_actions(self):
        enabled = self._ready and not self._busy
        self.apply.set_sensitive(enabled and self._selected is not None and bool(self.choices))
        self.restore.set_sensitive(enabled and any(self._metadata.values()))
        self.grid.set_sensitive(enabled)
        self.search.set_sensitive(enabled)
        self.cancel.set_sensitive(not self._busy)

    def _show_message(self, text, error=False):
        self.message.set_label(text)
        self.message.set_css_classes(["error"] if error else ["dim-label"])
        self.message.set_visible(True)

    def _save(self, name):
        if self._busy or not self._ready:
            return
        if name is not None and name not in {icon.name for icon in self.choices}:
            return
        self._busy = True
        self._update_actions()

        def work():
            error_text = None
            try:
                save_icon(self.folder, name, self._metadata)
            except Exception as error:
                error_text = str(error)
            GLib.idle_add(self._saved, error_text)

        threading.Thread(target=work, daemon=True).start()

    def _saved(self, error):
        self._busy = False
        if error:
            self._show_message(error, error=True)
            self._update_actions()
        else:
            self.close()
        return GLib.SOURCE_REMOVE

    def _close_requested(self, window):
        if not self._busy:
            self._destroyed(window)
        return self._busy

    def _destroyed(self, window):
        if self._theme_signal:
            self._theme.disconnect(self._theme_signal)
            self._theme_signal = 0


def main():
    if len(sys.argv) != 2:
        print("Usage: big-gnome-center-folder-icon FOLDER", file=sys.stderr)
        return 2
    folder = Gio.File.new_for_commandline_arg(sys.argv[1])
    app = Adw.Application(
        application_id=APP_ID + ".FolderIcon", flags=Gio.ApplicationFlags.NON_UNIQUE
    )
    app.connect("activate", lambda application: FolderIconWindow(application, folder).present())
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    sys.exit(main())
