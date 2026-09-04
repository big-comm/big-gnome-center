# SPDX-License-Identifier: MIT
"""Searchable application chooser for the startup applications page."""

from pathlib import Path
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

from constants import tr
from startup_manager import ApplicationCandidate, StartupManager


def application_icon(icon: str, size: int = 32) -> Gtk.Image:
    """Build an application icon from a themed name, serialized GIcon, or path."""
    if icon and Path(icon).is_file():
        image = Gtk.Image.new_from_file(icon)
    elif icon:
        try:
            image = Gtk.Image.new_from_gicon(Gio.Icon.new_for_string(icon))
        except GLib.Error:
            image = Gtk.Image.new_from_icon_name("application-x-executable-symbolic")
    else:
        image = Gtk.Image.new_from_icon_name("application-x-executable-symbolic")
    image.set_pixel_size(size)
    return image


class ApplicationRow(Adw.ActionRow):
    """Chooser row carrying its application candidate."""

    def __init__(self, candidate: ApplicationCandidate) -> None:
        super().__init__()
        self.candidate = candidate
        self.set_title(candidate.name)
        if candidate.description:
            self.set_subtitle(candidate.description)
            self.set_subtitle_lines(1)
        self.set_activatable(True)

        icon = application_icon(candidate.icon)
        icon.set_margin_start(4)
        self.add_prefix(icon)

        add_icon = Gtk.Image.new_from_icon_name("list-add-symbolic")
        add_icon.add_css_class("dim-label")
        self.add_suffix(add_icon)


class StartupApplicationDialog(Adw.Dialog):
    """List installed graphical applications and return the selected one."""

    def __init__(
        self,
        pool,
        excluded_ids: set[str],
        on_selected: Callable[[ApplicationCandidate], None],
    ) -> None:
        super().__init__()
        self._pool = pool
        self._excluded_ids = excluded_ids
        self._on_selected = on_selected
        self._query = ""

        self.set_title(tr("Add a startup application"))
        self.set_content_width(620)
        self.set_content_height(620)
        self._build()
        self._load()

    def _build(self) -> None:
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(12)
        content.set_margin_bottom(16)

        self._search = Gtk.SearchEntry(placeholder_text=tr("Search applications"))
        self._search.connect("search-changed", self._on_search_changed)
        content.append(self._search)

        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.set_vexpand(True)

        loading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        loading.set_valign(Gtk.Align.CENTER)
        spinner = Gtk.Spinner(spinning=True)
        spinner.set_size_request(32, 32)
        loading.append(spinner)
        loading_label = Gtk.Label(label=tr("Loading…"))
        loading_label.add_css_class("dim-label")
        loading.append(loading_label)
        self._stack.add_named(loading, "loading")

        empty = Adw.StatusPage(
            icon_name="system-search-symbolic",
            title=tr("No results"),
        )
        self._stack.add_named(empty, "empty")

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        self._list = Gtk.ListBox()
        self._list.add_css_class("boxed-list")
        self._list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list.set_filter_func(self._filter_row)
        self._list.connect("row-activated", self._on_row_activated)
        scroll.set_child(self._list)
        self._stack.add_named(scroll, "results")

        content.append(self._stack)
        toolbar.set_content(content)
        self.set_child(toolbar)

    def _load(self) -> None:
        self._stack.set_visible_child_name("loading")

        def task() -> None:
            candidates = StartupManager.list_applications(self._excluded_ids)
            GLib.idle_add(self._populate, candidates)

        self._pool.submit(task)

    def _populate(self, candidates: list[ApplicationCandidate]) -> bool:
        for candidate in candidates:
            self._list.append(ApplicationRow(candidate))
        self._update_stack()
        self._search.grab_focus()
        return False

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        self._query = entry.get_text().strip().casefold()
        self._list.invalidate_filter()
        self._update_stack()

    def _filter_row(self, row: ApplicationRow) -> bool:
        if not self._query:
            return True
        candidate = row.candidate
        searchable = "\n".join(
            (candidate.name, candidate.description, candidate.desktop_id)
        ).casefold()
        return self._query in searchable

    def _has_visible_rows(self) -> bool:
        child = self._list.get_first_child()
        while child is not None:
            if child.get_child_visible():
                return True
            child = child.get_next_sibling()
        return False

    def _update_stack(self) -> None:
        self._stack.set_visible_child_name("results" if self._has_visible_rows() else "empty")

    def _on_row_activated(self, list_box, row: ApplicationRow) -> None:
        self.close()
        self._on_selected(row.candidate)
