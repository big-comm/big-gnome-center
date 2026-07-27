# SPDX-License-Identifier: MIT
"""Static checks for the redesigned theme and effect galleries."""

import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EFFECTS = ROOT / "usr/share/layout-switcher/effects"


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
        assert icon in constants
        icon_source = (
            ROOT / f"usr/share/icons/hicolor/scalable/actions/{icon}.svg"
        ).read_text()
        assert "Font Awesome Free 6.7.2" in icon_source
        assert "Icons: CC BY 4.0" in icon_source

    license_text = (
        ROOT / "usr/share/licenses/layout-switcher/FONT-AWESOME-LICENSE.txt"
    ).read_text()
    assert "Creative Commons" in license_text
    assert "Attribution 4.0 International" in license_text
