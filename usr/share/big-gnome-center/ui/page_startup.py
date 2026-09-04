# SPDX-License-Identifier: MIT
"""Startup applications management page."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from constants import tr
from startup_manager import ApplicationCandidate, StartupEntry, StartupManager
from ui.dialog_startup_apps import StartupApplicationDialog, application_icon


class StartupPage(Gtk.Box):
    """List, add, and remove effective XDG autostart entries."""

    def __init__(self, pool, toast_cb) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._pool = pool
        self._toast = toast_cb
        self._manager = StartupManager()
        self._entries: list[StartupEntry] = []
        self._rows: list[Gtk.Widget] = []
        self._refresh_token = 0
        self._build()
        self.refresh()

    def _build(self) -> None:
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(760)
        clamp.set_tightening_threshold(560)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.set_margin_start(22)
        content.set_margin_end(22)
        content.set_margin_top(20)
        content.set_margin_bottom(24)

        self._group = Adw.PreferencesGroup(
            title=tr("Startup Applications"),
            description=tr("Startup applications are automatically started when you log in."),
        )
        add_button = Gtk.Button.new_from_icon_name("list-add-symbolic")
        add_button.add_css_class("flat")
        add_button.add_css_class("circular")
        add_button.set_tooltip_text(tr("Add a startup application"))
        add_button.update_property(
            [Gtk.AccessibleProperty.LABEL],
            [tr("Add a startup application")],
        )
        add_button.connect("clicked", self._on_add_clicked)
        self._group.set_header_suffix(add_button)
        content.append(self._group)

        clamp.set_child(content)
        scroll.set_child(clamp)
        self.append(scroll)

    def refresh(self) -> None:
        """Reload entries without blocking the GTK main thread."""
        self._refresh_token += 1
        token = self._refresh_token

        def task() -> None:
            entries = self._manager.list_entries()
            GLib.idle_add(self._render, token, entries)

        self._pool.submit(task)

    def _clear_rows(self) -> None:
        for row in self._rows:
            self._group.remove(row)
        self._rows.clear()

    def _render(self, token: int, entries: list[StartupEntry]) -> bool:
        if token != self._refresh_token:
            return False
        self._entries = entries
        self._clear_rows()
        if not entries:
            empty = Adw.ActionRow(
                title=tr("No Startup Applications"),
            )
            empty.set_sensitive(False)
            empty_icon = Gtk.Image.new_from_icon_name("system-run-symbolic")
            empty_icon.set_pixel_size(32)
            empty.add_prefix(empty_icon)
            self._group.add(empty)
            self._rows.append(empty)
            return False

        for entry in entries:
            row = self._make_row(entry)
            self._group.add(row)
            self._rows.append(row)
        return False

    def _make_row(self, entry: StartupEntry) -> Adw.ActionRow:
        row = Adw.ActionRow(title=entry.name)
        if entry.description:
            row.set_subtitle(entry.description)
            row.set_subtitle_lines(1)

        icon = application_icon(entry.icon)
        icon.set_margin_start(4)
        row.add_prefix(icon)

        remove_button = Gtk.Button.new_from_icon_name("user-trash-symbolic")
        remove_button.add_css_class("flat")
        remove_button.set_valign(Gtk.Align.CENTER)
        remove_button.set_tooltip_text(tr("Remove"))
        remove_button.update_property(
            [Gtk.AccessibleProperty.LABEL],
            [tr("Remove")],
        )
        remove_button.connect(
            "clicked",
            lambda button, item=entry: self._remove(item, button),
        )
        row.add_suffix(remove_button)
        return row

    def _on_add_clicked(self, button: Gtk.Button) -> None:
        excluded_ids = {entry.desktop_id for entry in self._entries}
        dialog = StartupApplicationDialog(
            pool=self._pool,
            excluded_ids=excluded_ids,
            on_selected=self._add,
        )
        root = self.get_root()
        dialog.present(root if isinstance(root, Gtk.Window) else self)

    def _add(self, candidate: ApplicationCandidate) -> None:
        def task() -> None:
            ok, error = self._manager.add_application(candidate.source)
            GLib.idle_add(self._on_add_done, ok, error, candidate.name)

        self._pool.submit(task)

    def _on_add_done(self, ok: bool, error: str, name: str) -> bool:
        if ok:
            self._toast(name)
            self.refresh()
        else:
            self._toast(tr("Error"))
        return False

    def _remove(self, entry: StartupEntry, button: Gtk.Button) -> None:
        button.set_sensitive(False)

        def task() -> None:
            ok, error = self._manager.remove(entry.desktop_id)
            GLib.idle_add(self._on_remove_done, ok, error, entry.name)

        self._pool.submit(task)

    def _on_remove_done(self, ok: bool, error: str, name: str) -> bool:
        if ok:
            self._toast(name)
            self.refresh()
        else:
            self._toast(tr("Error"))
            self.refresh()
        return False
