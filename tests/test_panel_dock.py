# SPDX-License-Identifier: MIT
"""Panel and Dock UI and settings contracts."""

from pathlib import Path

from panel_dock_settings import PanelDockSettings

ROOT = Path(__file__).resolve().parents[1]


class FakeSettings:
    def __init__(self, values):
        self.values = dict(values)

    def get_boolean(self, key):
        return self.values[key]

    def set_boolean(self, key, value):
        self.values[key] = value

    def get_double(self, key):
        return self.values[key]

    def set_double(self, key, value):
        self.values[key] = value

    def set_enum(self, key, value):
        self.values[key] = value

    def get_uint(self, key):
        return self.values[key]

    def set_uint(self, key, value):
        self.values[key] = value

    def get_int(self, key):
        return self.values[key]

    def set_int(self, key, value):
        self.values[key] = value

    def get_string(self, key):
        return self.values[key]

    def set_string(self, key, value):
        self.values[key] = value


def settings_fixture():
    settings = PanelDockSettings.__new__(PanelDockSettings)
    settings.dock_active = True
    settings.community_panel_active = False
    settings.dock = FakeSettings(
        {
            "background-opacity": 0.77,
            "custom-background-color": True,
            "transparency-mode": 1,
            "manualhide": False,
            "dock-fixed": False,
            "intellihide": True,
            "autohide": True,
            "running-indicator-style": 0,
        }
    )
    settings.panel = FakeSettings(
        {
            "panel-opacity": 65,
            "panel-visibility": "always-visible",
            "indicator-style": "dot",
        }
    )
    settings.community_panel = FakeSettings(
        {
            "trans-panel-opacity": 0.7,
            "trans-use-custom-opacity": True,
            "trans-use-dynamic-opacity": False,
            "intellihide": False,
            "intellihide-hide-from-windows": False,
            "intellihide-hide-from-monitor-windows": False,
            "intellihide-behaviour": "FOCUSED_WINDOWS",
            "intellihide-use-pointer": True,
            "dot-style-focused": "SEGMENTED",
            "dot-style-unfocused": "SEGMENTED",
            "dot-size": 3,
        }
    )
    return settings


def test_dock_opacity_preserves_fixed_custom_background():
    settings = settings_fixture()

    settings.set_dock_opacity(42)

    assert settings.dock_opacity() == 42
    assert settings.dock.values["custom-background-color"] is True
    assert settings.dock.values["transparency-mode"] == 1


def test_dock_visibility_maps_all_three_modes():
    settings = settings_fixture()

    settings.set_dock_visibility("always-visible")
    assert settings.dock_visibility() == "always-visible"
    assert settings.dock.values["dock-fixed"] is True

    settings.set_dock_visibility("always-hidden")
    assert settings.dock_visibility() == "always-hidden"
    assert settings.dock.values["manualhide"] is False
    assert settings.dock.values["dock-fixed"] is False
    assert settings.dock.values["intellihide"] is False
    assert settings.dock.values["autohide"] is True

    settings.set_dock_visibility("intelligent")
    assert settings.dock_visibility() == "intelligent"
    assert settings.dock.values["intellihide"] is True
    assert settings.dock.values["autohide"] is True


def test_panel_settings_clamp_opacity_and_validate_visibility():
    settings = settings_fixture()

    settings.set_panel_opacity(130)
    settings.set_panel_visibility("intelligent")

    assert settings.panel_opacity() == 100
    assert settings.panel_visibility() == "intelligent"


def test_community_panel_opacity_maps_to_dash_to_panel_schema():
    settings = settings_fixture()
    settings.community_panel_active = True

    settings.set_panel_opacity(43)

    assert settings.panel_opacity() == 43
    assert settings.community_panel.values["trans-use-custom-opacity"] is True
    assert settings.community_panel.values["trans-use-dynamic-opacity"] is False


def test_community_panel_visibility_maps_all_three_modes():
    settings = settings_fixture()
    settings.community_panel_active = True

    settings.set_panel_visibility("always-visible")
    assert settings.panel_visibility() == "always-visible"
    assert settings.community_panel.values["intellihide"] is False

    settings.set_panel_visibility("always-hidden")
    assert settings.panel_visibility() == "always-hidden"
    assert settings.community_panel.values["intellihide"] is True
    assert settings.community_panel.values["intellihide-hide-from-windows"] is False

    settings.set_panel_visibility("intelligent")
    assert settings.panel_visibility() == "intelligent"
    assert settings.community_panel.values["intellihide-hide-from-windows"] is True
    assert settings.community_panel.values["intellihide-use-pointer"] is True


def test_indicator_style_updates_custom_schema_and_uses_native_dot():
    settings = settings_fixture()

    settings.set_indicator_style("hybrid")

    assert settings.indicator_style() == "hybrid"
    assert settings.panel.values["indicator-style"] == "hybrid"
    assert settings.dock.values["running-indicator-style"] == 0


def test_community_panel_indicator_styles_map_to_native_taskbar_styles():
    settings = settings_fixture()
    settings.community_panel_active = True

    assert settings.indicator_style() == "hybrid"

    settings.set_indicator_style("desk-ux")
    assert settings.indicator_style() == "desk-ux"
    assert settings.community_panel.values["dot-style-focused"] == "METRO"
    assert settings.community_panel.values["dot-style-unfocused"] == "DASHES"
    assert settings.community_panel.values["dot-size"] == 3

    settings.set_indicator_style("dot")
    assert settings.indicator_style() == "dot"
    assert settings.community_panel.values["dot-style-focused"] == "DOTS"
    assert settings.community_panel.values["dot-size"] == 6


def test_window_exposes_panel_and_dock_navigation():
    window = (ROOT / "usr/share/layout-switcher/ui/window.py").read_text()

    assert "from ui.page_panel_dock import PanelDockPage" in window
    assert '"panel-dock": lambda: PanelDockPage' in window
    assert 'tr("Panel and Dock")' in window
    assert 'elif key == "panel-dock":' in window


def test_minimal_disables_panel_and_dock_navigation():
    window = (ROOT / "usr/share/layout-switcher/ui/window.py").read_text()
    layouts = (ROOT / "usr/share/layout-switcher/ui/page_layouts.py").read_text()

    assert "def refresh_layout_capabilities(self)" in window
    assert 'Settings().get("active_layout", "") != "Minimal"' in window
    assert "panel_dock_row.set_sensitive(panel_dock_available)" in window
    assert 'self._nav.select_row(self._nav_rows["layouts"])' in window
    assert layouts.count("root.refresh_layout_capabilities()") == 2


def test_page_exposes_opacity_and_visibility_controls():
    page = (ROOT / "usr/share/layout-switcher/ui/page_panel_dock.py").read_text()

    assert 'tr("Dock transparency")' in page
    assert 'tr("Panel transparency")' in page
    assert 'tr("Dock visibility")' in page
    assert 'tr("Panel visibility")' in page
    assert 'tr("Always visible")' in page
    assert 'tr("Always hidden (show at edge)")' in page
    assert 'tr("Intelligent hiding")' in page
    assert 'tr("Running app indicator")' in page
    assert 'tr("Dot")' in page
    assert 'tr("Hybrid line")' in page
    assert 'tr("Desk UX line")' in page
    assert "_build_indicator_preview" in page
    assert '"dot": ((6, 6), (6, 6))' in page
    assert '"hybrid": ((20, 4), (20, 4))' in page
    assert '"desk-ux": ((8, 3), (18, 3))' in page
    assert "indicator.set_halign(Gtk.Align.CENTER)" in page
    assert "PanelDockSettings" in page
    assert "COMMUNITY_PANEL_UUID" in page
    assert "dock_available" in page
    assert "panel_available" in page
    assert "indicator_available" in page
    assert 'active_layout = Settings().get("active_layout", "")' in page
    assert 'self._dock_group.set_visible(active_layout != "Classic")' in page
    assert 'tr("Taskbar")' in page
    assert 'tr("Configure running application indicators.")' in page
    assert "self._dock_opacity.set_visible(not community_panel_active)" in page
    assert 'tr("Configure the Community Panel appearance and visibility.")' in page
