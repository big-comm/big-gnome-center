# SPDX-License-Identifier: MIT
"""Static checks for the redesigned theme and effect galleries."""

import struct
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EFFECTS = ROOT / "usr/share/layout-switcher/effects"


def test_application_icon_has_large_intrinsic_size():
    icon = ROOT / "usr/share/icons/hicolor/scalable/apps/layout-switcher.svg"
    root = ET.parse(icon).getroot()

    assert root.attrib["width"] == "128"
    assert root.attrib["height"] == "128"


def test_shared_menu_icon_has_shell_button_size():
    icon = ROOT / "usr/share/icons/hicolor/scalable/apps/bigcommunity-menu-symbolic.svg"
    root = ET.parse(icon).getroot()

    assert root.attrib["width"] == "48"
    assert root.attrib["height"] == "48"
    source = icon.read_text()
    assert "#808080" in source
    assert "#2c2734" not in source
    assert "#f2f2f2" not in source


def test_update_notification_opens_installed_extensions():
    main_source = (ROOT / "usr/share/layout-switcher/main.py").read_text()
    window_source = (ROOT / "usr/share/layout-switcher/ui/window.py").read_text()
    extensions_source = (ROOT / "usr/share/layout-switcher/ui/page_extensions.py").read_text()

    assert "Gio.ApplicationFlags.HANDLES_COMMAND_LINE" in main_source
    assert '"--extensions-updates"' in main_source
    assert "win.show_extension_updates()" in main_source
    assert "def show_extension_updates(self)" in window_source
    assert 'self._nav_rows["extensions"]' in window_source
    assert "page.show_installed()" in window_source
    assert 'self._switch_sub("installed")' in extensions_source


def test_extension_search_defaults_to_relevance():
    source = (ROOT / "usr/share/layout-switcher/ui/ext_browse_view.py").read_text()

    relevance = '(tr("Relevance"), ego_client.SORT_RELEVANCE)'
    popularity = '(tr("Popularity"), ego_client.SORT_POPULARITY)'
    assert source.index(relevance) < source.index(popularity)
    assert "self._sort = ego_client.SORT_RELEVANCE" in source


def test_extension_search_discards_stale_async_results():
    source = (ROOT / "usr/share/layout-switcher/ui/ext_browse_view.py").read_text()

    assert "self._search_generation += 1" in source
    assert "generation = self._search_generation" in source
    assert "GLib.idle_add(self._on_search_done, generation, result)" in source
    assert "if generation != self._search_generation:" in source
    assert source.count("self._search_generation += 1") == 2
    assert "if self._loading:\n            return" not in source


def test_effect_assets_and_gallery_geometry():
    for name in ("cube.png", "lamp.png", "wobbly.png"):
        path = EFFECTS / name
        data = path.read_bytes()
        assert data.startswith(b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", data[16:24])
        assert (width, height) == (600, 338)
        assert 100_000 <= len(data) <= 200_000

    effects_source = (ROOT / "usr/share/layout-switcher/ui/page_effects.py").read_text()
    themes_source = (ROOT / "usr/share/layout-switcher/ui/page_themes.py").read_text()

    assert "set_max_children_per_line(2)" in effects_source
    assert "set_min_children_per_line(2)" in effects_source
    assert "Gtk.ContentFit.CONTAIN" in effects_source
    assert "Gtk.Picture.new_for_filename" in effects_source
    assert "icon_frame = Gtk.CenterBox()" in effects_source
    assert "icon_frame.set_center_widget(ico)" in effects_source
    assert "set_max_children_per_line(5)" in themes_source
    assert "set_size_request(128, 68)" in themes_source
    assert 'self._section = "accent"' in themes_source
    assert themes_source.index('("accent", tr("Colors"))') < themes_source.index(
        '("icons", tr("Icons"))'
    )
    assert themes_source.index('("icons", tr("Icons"))') < themes_source.index(
        '("cursors", tr("Cursors"))'
    )
    assert "CursorStrip(find_theme_cursors(name), slot_size=22)" in themes_source
    assert 'ThemeMgr.apply(kind, name)' in themes_source
    assert 'tr("Applications")' not in themes_source
    assert 'tr("Shell")' not in themes_source
    assert "ThemeMgr.set_accent_color(color)" in themes_source
    assert "ColorDot(hex_value, size=26)" in themes_source
    assert "set_accessible_name" not in themes_source
    assert "Gtk.AccessibleProperty.LABEL" in themes_source
    assert 'tabs.add_css_class("linked")' not in themes_source
    assert "Gtk.Orientation.HORIZONTAL, spacing=4" in themes_source
    assert "tabs.set_margin_top(8)" in themes_source
    assert "tabs.set_margin_bottom(10)" in themes_source
    assert "self.append(self._build_section_tabs())" in themes_source
    assert "surface.append(self._build_section_tabs())" not in themes_source

    constants = (ROOT / "usr/share/layout-switcher/constants.py").read_text()
    for icon in (
        "layout-effect-cube-symbolic",
        "layout-effect-lamp-symbolic",
        "layout-effect-wobbly-symbolic",
    ):
        icon_source = (ROOT / f"usr/share/icons/hicolor/scalable/actions/{icon}.svg").read_text()
        assert "Font Awesome Free 6.7.2" in icon_source
        assert "Icons: CC BY 4.0" in icon_source

    window_source = (ROOT / "usr/share/layout-switcher/ui/window.py").read_text()
    assert "layout-effect-cube-symbolic" in constants
    assert "layout-effect-wobbly-symbolic" in constants
    assert '("effects", tr("Effects"), "layout-effect-lamp-symbolic")' in window_source

    genie_icon = (
        ROOT / "usr/share/icons/hicolor/scalable/actions/layout-effect-genie-lamp-symbolic.svg"
    ).read_text()
    assert "<title>Genie lamp</title>" in genie_icon
    assert 'stroke="currentColor"' in genie_icon

    assert '"icon": "layout-effect-genie-lamp-symbolic"' in constants

    license_text = (
        ROOT / "usr/share/licenses/layout-switcher/FONT-AWESOME-LICENSE.txt"
    ).read_text()
    assert "Creative Commons" in license_text
    assert "Attribution 4.0 International" in license_text
