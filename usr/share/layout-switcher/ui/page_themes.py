# SPDX-License-Identifier: MIT
"""Accent color and icon theme settings."""

from typing import Dict, List

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Pango", "1.0")
from gi.repository import Adw, GLib, Gtk, Pango

from constants import ACCENT_COLORS, tr
from theme_manager import ThemeMgr
from theme_preview import find_theme_icons
from ui.widgets import ColorDot, IconStrip

_LIST_MAX_WIDTH = 940
_ACCENT_LABELS = {
    "blue": tr("Blue"),
    "teal": tr("Teal"),
    "green": tr("Green"),
    "yellow": tr("Yellow"),
    "orange": tr("Orange"),
    "red": tr("Red"),
    "pink": tr("Pink"),
    "purple": tr("Purple"),
    "slate": tr("Slate"),
    "maia": tr("Maia"),
}


class ThemeTile(Gtk.FlowBoxChild):
    """Icon theme tile with a typed theme name."""

    def __init__(self, theme_name: str) -> None:
        super().__init__()
        self._theme_name = theme_name

    @property
    def theme_name(self) -> str:
        return self._theme_name


class ThemesPage(Gtk.Box):
    """Unified accent color and icon theme page."""

    def __init__(self, pool, toast_cb) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._pool = pool
        self._toast = toast_cb
        self._section = "accent"
        self._cached_names: List[str] = []
        self._cached_active = ""
        self._build()

    def _build(self) -> None:
        self.append(self._build_section_tabs())

        surface = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        surface.add_css_class("theme-surface")
        surface.set_margin_start(14)
        surface.set_margin_end(14)
        surface.set_margin_bottom(10)
        surface.set_vexpand(True)

        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_placeholder_text(tr("Filter themes…"))
        self._search_entry.set_margin_start(26)
        self._search_entry.set_margin_end(26)
        self._search_entry.set_margin_top(12)
        self._search_entry.set_margin_bottom(8)
        self._search_entry.set_visible(False)
        self._search_entry.connect("search-changed", self._on_search_changed)
        surface.append(self._search_entry)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(_LIST_MAX_WIDTH)
        clamp.set_tightening_threshold(460)

        self._list_container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )
        self._list_container.set_margin_start(16)
        self._list_container.set_margin_end(16)
        self._list_container.set_margin_top(6)
        self._list_container.set_margin_bottom(24)
        clamp.set_child(self._list_container)
        scroller.set_child(clamp)
        surface.append(scroller)
        self.append(surface)

        self.refresh_themes()

    def _build_section_tabs(self) -> Gtk.Widget:
        tabs = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        tabs.set_margin_start(26)
        tabs.set_margin_end(22)
        tabs.set_margin_top(8)
        tabs.set_margin_bottom(10)
        self._section_buttons: Dict[str, Gtk.Button] = {}
        for section, label in [
            ("accent", tr("Colors")),
            ("icons", tr("Icons")),
        ]:
            button = Gtk.Button(label=label)
            button.add_css_class("kind-tab")
            button.add_css_class("flat")
            if section == "accent":
                button.add_css_class("kind-on")
            button.connect(
                "clicked",
                lambda _button, target=section: self._switch_section(target),
            )
            tabs.append(button)
            self._section_buttons[section] = button
        return tabs

    def _switch_section(self, section: str) -> None:
        self._section = section
        self._search_entry.set_visible(section == "icons")
        for key, button in self._section_buttons.items():
            if key == section:
                button.add_css_class("kind-on")
            else:
                button.remove_css_class("kind-on")
        self.refresh_themes()

    def _clear_content(self) -> None:
        child = self._list_container.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self._list_container.remove(child)
            child = next_child

    def refresh_themes(self) -> None:
        """Refresh the active section."""
        self._clear_content()
        if self._section == "accent":
            self._populate_accents()
            return

        spinner = Gtk.Spinner(spinning=True)
        spinner.set_halign(Gtk.Align.CENTER)
        spinner.set_valign(Gtk.Align.CENTER)
        spinner.set_margin_top(48)
        spinner.set_size_request(32, 32)
        self._list_container.append(spinner)

        def scan() -> None:
            active = ThemeMgr.current("icons")
            names = ThemeMgr.list_themes("icons")
            GLib.idle_add(self._populate_icons, active, names)

        self._pool.submit(scan)

    def _populate_accents(self) -> None:
        active = ThemeMgr.accent_color()

        title = Gtk.Label(label=tr("Accent color"))
        title.add_css_class("heading")
        title.set_halign(Gtk.Align.START)
        title.set_margin_start(10)
        title.set_margin_end(10)
        title.set_margin_top(18)
        self._list_container.append(title)

        description = Gtk.Label(
            label=tr("Choose the color used for buttons, selections, and highlights.")
        )
        description.add_css_class("dim-label")
        description.set_halign(Gtk.Align.START)
        description.set_wrap(True)
        description.set_margin_start(10)
        description.set_margin_end(10)
        description.set_margin_top(4)
        description.set_margin_bottom(14)
        self._list_container.append(description)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.add_css_class("accent-color-card")

        colors = Gtk.FlowBox()
        colors.set_selection_mode(Gtk.SelectionMode.NONE)
        colors.set_halign(Gtk.Align.CENTER)
        colors.set_max_children_per_line(len(ACCENT_COLORS))
        colors.set_min_children_per_line(3)
        colors.set_row_spacing(8)
        colors.set_column_spacing(8)
        colors.set_homogeneous(True)

        for color, hex_value in ACCENT_COLORS.items():
            label = _ACCENT_LABELS[color]
            button = Gtk.Button()
            button.add_css_class("accent-color-choice")
            button.add_css_class("flat")
            if color == active:
                button.add_css_class("accent-color-active")
            button.set_tooltip_text(label)
            button.update_property(
                [Gtk.AccessibleProperty.LABEL],
                [tr("{color} accent color").format(color=label)],
            )
            button.set_child(ColorDot(hex_value, size=26))
            button.connect(
                "clicked",
                lambda _button, selected=color: self._apply_accent(selected),
            )
            colors.append(button)

        card.append(colors)
        self._list_container.append(card)

    def _populate_icons(self, active: str, names: List[str]) -> None:
        self._cached_names = names
        self._cached_active = active
        self._filter_and_display_icons(active, names)

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        if self._section != "icons":
            return
        query = entry.get_text().strip().lower()
        names = (
            [name for name in self._cached_names if query in name.lower()]
            if query
            else self._cached_names
        )
        self._filter_and_display_icons(self._cached_active, names)

    def _filter_and_display_icons(self, active: str, names: List[str]) -> None:
        self._clear_content()
        if not names:
            self._list_container.append(
                Adw.StatusPage(
                    title=tr("No themes found"),
                    description=tr("Install themes to ~/.themes or /usr/share/themes"),
                    icon_name="preferences-desktop-theme-symbolic",
                )
            )
            return

        count_label = Gtk.Label(label=tr("{n} themes available").format(n=len(names)))
        count_label.add_css_class("caption")
        count_label.add_css_class("dim-label")
        count_label.set_halign(Gtk.Align.START)
        count_label.set_margin_bottom(8)
        self._list_container.append(count_label)
        self._list_container.append(self._build_icon_grid(active, names))

    def _build_icon_grid(self, active: str, names: List[str]) -> Gtk.Widget:
        grid = Gtk.FlowBox()
        grid.set_selection_mode(Gtk.SelectionMode.NONE)
        grid.set_max_children_per_line(5)
        grid.set_min_children_per_line(1)
        grid.set_row_spacing(10)
        grid.set_column_spacing(10)
        grid.set_homogeneous(True)
        grid.connect(
            "child-activated",
            lambda _grid, tile: self._apply_icon_theme(tile.theme_name),
        )
        for name in names:
            grid.append(self._make_icon_tile(name, active))
        return grid

    def _make_icon_tile(self, name: str, active: str) -> ThemeTile:
        is_active = name == active
        tile = ThemeTile(theme_name=name)
        tile.add_css_class("theme-tile")
        tile.set_size_request(142, -1)
        if is_active:
            tile.add_css_class("theme-tile-active")

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        content.set_margin_start(7)
        content.set_margin_end(7)
        content.set_margin_top(7)
        content.set_margin_bottom(7)

        preview = Gtk.Box()
        preview.add_css_class("theme-icon-preview")
        preview.set_size_request(128, 68)
        strip = IconStrip(find_theme_icons(name), slot_size=22)
        strip.set_halign(Gtk.Align.CENTER)
        strip.set_valign(Gtk.Align.CENTER)
        preview.append(strip)

        overlay = Gtk.Overlay()
        overlay.set_child(preview)
        if is_active:
            check = Gtk.Image.new_from_icon_name("object-select-symbolic")
            check.set_pixel_size(13)
            check.add_css_class("theme-active-check")
            check.set_halign(Gtk.Align.END)
            check.set_valign(Gtk.Align.START)
            check.set_margin_top(3)
            check.set_margin_end(3)
            overlay.add_overlay(check)
        content.append(overlay)

        label = Gtk.Label(label=name)
        label.add_css_class("body")
        if is_active:
            label.add_css_class("theme-name-active")
        label.set_halign(Gtk.Align.START)
        label.set_xalign(0)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        content.append(label)
        tile.set_child(content)

        accessible_label = tr("{name} theme").format(name=name)
        if is_active:
            accessible_label += " (" + tr("Active") + ")"
        tile.update_property(
            [Gtk.AccessibleProperty.LABEL],
            [accessible_label],
        )
        return tile

    def _apply_accent(self, color: str) -> None:
        def task() -> None:
            ok, error = ThemeMgr.set_accent_color(color)
            if ok:
                GLib.idle_add(self._toast, _ACCENT_LABELS[color])
                GLib.idle_add(self.refresh_themes)
            else:
                GLib.idle_add(self._toast, tr("Error") + f": {error}")

        self._pool.submit(task)

    def _apply_icon_theme(self, name: str) -> None:
        def task() -> None:
            ok, error = ThemeMgr.apply("icons", name)
            if ok:
                GLib.idle_add(self._toast, name)
                GLib.idle_add(self.refresh_themes)
            else:
                GLib.idle_add(self._toast, tr("Error") + f": {error}")

        self._pool.submit(task)
