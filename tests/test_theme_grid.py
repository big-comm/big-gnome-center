# SPDX-License-Identifier: MIT
"""Keep cursor gallery columns stable when the active label changes."""

import unittest

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk

from ui.page_themes import ThemesPage
from ui.styles import APP_CSS


class _Gallery:
    _make_theme_tile = ThemesPage._make_theme_tile

    def _apply_theme(self, *_args):
        pass


def test_cursor_columns_survive_selection_and_long_names():
    if not Gtk.init_check():
        raise unittest.SkipTest("Requires a GTK display")
    Adw.init()
    display = Gdk.Display.get_default()
    provider = Gtk.CssProvider()
    provider.load_from_string(APP_CSS)
    Gtk.StyleContext.add_provider_for_display(display, provider, 800)
    names = [
        "Adwaita",
        "Bibata-Modern-Amber",
        "Bibata-Modern-Amber-Right",
        "Bibata-Modern-Black-Orange",
        "Bibata-Modern-Classic",
        "Bibata-Modern-Classic-Right",
        "Bibata-Modern-Ice",
        "Bibata-Modern-Ice-Right",
        "Bibata-Modern-Orange-Black",
        "Custom-Cursor-Theme-With-A-Very-Long-Name",
    ]
    try:
        for active in (names[4], names[3], names[8], names[-1], names[4]):
            grid = ThemesPage._build_theme_grid(_Gallery(), active, names, "cursors")
            for width, columns in ((640, 3), (660, 3), (900, 3), (400, 2), (320, 1)):
                grid.allocate(width, 1000, -1, None)
                bounds = [
                    grid.get_child_at_index(i).compute_bounds(grid)[1]
                    for i in range(len(names))
                ]
                assert sum(rect.origin.y == bounds[0].origin.y for rect in bounds) == columns
                assert all(rect.origin.x + rect.size.width <= width for rect in bounds)
    finally:
        Gtk.StyleContext.remove_provider_for_display(display, provider)


if __name__ == "__main__":
    test_cursor_columns_survive_selection_and_long_names()
    print("Cursor gallery: selection, long names and narrow widths passed")
