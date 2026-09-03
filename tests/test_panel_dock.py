# SPDX-License-Identifier: MIT
"""Panel and Dock UI and settings contracts."""

import gettext
from pathlib import Path

import pytest

from panel_dock_settings import PanelDockSettings
from runtime_settings import LAYOUT_DEFAULTS, RuntimeSettings

ROOT = Path(__file__).resolve().parents[1]
APP_LOCALES = (
    "bg", "cs", "da", "de", "el", "en", "es", "et", "fi", "fr", "he",
    "hr", "hu", "is", "it", "ja", "ko", "nl", "no", "pl", "pt_BR", "pt",
    "ro", "ru", "sk", "sv", "tr", "uk", "zh",
)


class FakeSettings:
    def __init__(self, values):
        self.values = dict(values)
        self.calls = []

    def get_boolean(self, key):
        return self.values[key]

    def set_boolean(self, key, value):
        self.calls.append(("set_boolean", key, value))
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
        self.calls.append(("set_int", key, value))
        self.values[key] = value

    def get_string(self, key):
        return self.values[key]

    def set_string(self, key, value):
        self.calls.append(("set_string", key, value))
        self.values[key] = value

    def get_value(self, key):
        return FakeVariant(dict(self.values[key]))

    def set_value(self, key, value):
        self.values[key] = value.unpack()


class FakeRuntime:
    def __init__(self):
        self.values = {}
        self.imported = set()
        self.active_layout = ""

    def supports_layout(self, layout):
        return layout in LAYOUT_DEFAULTS

    def set(self, layout, setting, value):
        self.values[(layout, setting)] = value

    def get(self, layout, setting, fallback=None):
        return self.values.get(
            (layout, setting),
            LAYOUT_DEFAULTS.get(layout, {}).get(setting, fallback),
        )

    def is_imported(self, layout):
        return layout in self.imported

    def mark_imported(self, layout):
        self.imported.add(layout)

    def set_active_layout(self, layout):
        self.active_layout = layout

    def default(self, layout, setting, fallback=None):
        return LAYOUT_DEFAULTS.get(layout, {}).get(setting, fallback)

    def reset_layout(self, layout, settings=None):
        selected = set(settings) if settings is not None else None
        self.values = {
            key: value
            for key, value in self.values.items()
            if key[0] != layout or (selected is not None and key[1] not in selected)
        }


class FakeVariant:
    def __init__(self, value):
        self.value = value

    def unpack(self):
        return self.value


class FakeRuntimeBackend:
    def __init__(self):
        self.values = {
            "active-layout": "",
            "imported-layouts": [],
            "dock-opacity-overrides": {},
            "dock-visibility-overrides": {},
            "panel-opacity-overrides": {},
            "panel-visibility-overrides": {},
            "indicator-style-overrides": {},
            "dock-size-overrides": {},
            "panel-height-overrides": {},
            "dock-hover-overrides": {},
            "dock-magnification-overrides": {},
            "dock-menu-side-overrides": {},
            "skip-startup-overview-overrides": {},
        }

    def get_value(self, key):
        return FakeVariant(dict(self.values[key]))

    def set_value(self, key, value):
        self.values[key] = value.unpack()

    def get_strv(self, key):
        return list(self.values[key])

    def set_strv(self, key, value):
        self.values[key] = list(value)

    def set_string(self, key, value):
        self.values[key] = value


def settings_fixture():
    settings = PanelDockSettings.__new__(PanelDockSettings)
    settings.active_layout = ""
    settings.dock_active = True
    settings.community_panel_active = False
    settings.runtime_active = False
    settings.runtime = FakeRuntime()
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
            "dash-max-icon-size": 39,
        }
    )
    settings.panel = FakeSettings(
        {
            "panel-opacity": 65,
            "panel-visibility": "always-visible",
            "indicator-style": "dot",
            "dock-hover-effect": "default",
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
            "panel-sizes": '{"0":38}',
            "animate-appicon-hover": False,
            "animate-appicon-hover-animation-type": "SIMPLE",
            "animate-appicon-hover-animation-convexity": {"SIMPLE": 0.0},
            "animate-appicon-hover-animation-duration": {"SIMPLE": 220},
            "animate-appicon-hover-animation-extent": {"SIMPLE": 1},
            "animate-appicon-hover-animation-rotation": {"SIMPLE": 0},
            "animate-appicon-hover-animation-travel": {"SIMPLE": 0.08},
            "animate-appicon-hover-animation-zoom": {"SIMPLE": 1.08},
        }
    )
    return settings


def test_runtime_defaults_match_accepted_layout_contracts():
    runtime = RuntimeSettings(FakeRuntimeBackend())

    assert runtime.get("BigGnome", "dock-opacity") == 77
    assert runtime.get("G-Unity", "dock-opacity") == 70
    assert runtime.get("G-Unity", "panel-opacity") == 70
    assert runtime.get("G-Unity", "dock-visibility") == "always-visible"
    assert runtime.get("BigGnome", "indicator-style") == "desk-ux"
    assert runtime.get("G-Unity", "indicator-style") == "dot"
    assert runtime.get("Hybrid", "indicator-style") == "hybrid"
    assert runtime.get("Desk UX", "indicator-style") == "desk-ux"
    assert runtime.get("Desk UX", "panel-height") == 40
    assert runtime.get("Desk UX", "dock-hover") == "default"
    assert runtime.get("Classic", "panel-height") == 38
    assert runtime.get("Minimal", "panel-opacity") == 65
    assert runtime.get("BigGnome", "dock-menu-side") == "right"
    assert runtime.get("BigGnome", "dock-magnification") == 40
    assert runtime.get("G-Unity", "dock-magnification") == 40
    assert runtime.get("BigGnome", "skip-startup-overview") is False
    assert runtime.get("G-Unity", "skip-startup-overview") is False
    assert runtime.get("Hybrid", "skip-startup-overview") is True
    assert runtime.get("Desk UX", "skip-startup-overview") is True
    assert runtime.get("Classic", "skip-startup-overview") is True
    assert runtime.get("Minimal", "skip-startup-overview") is False
    assert runtime.default("Minimal", "dock-size") is None


def test_runtime_keeps_overrides_per_layout_and_can_reset_one_layout():
    runtime = RuntimeSettings(FakeRuntimeBackend())

    runtime.set("BigGnome", "dock-opacity", 48)
    runtime.set("G-Unity", "dock-opacity", 72)
    runtime.reset_layout("BigGnome")

    assert runtime.get("BigGnome", "dock-opacity") == 77
    assert runtime.get("G-Unity", "dock-opacity") == 72


def test_runtime_can_reset_selected_settings_only():
    runtime = RuntimeSettings(FakeRuntimeBackend())
    runtime.set("BigGnome", "dock-opacity", 48)
    runtime.set("BigGnome", "dock-size", 54)

    runtime.reset_layout("BigGnome", {"dock-size"})

    assert runtime.get("BigGnome", "dock-opacity") == 48
    assert runtime.get("BigGnome", "dock-size") == 39


def test_runtime_serializes_original_reset_without_touching_other_layouts():
    backend = FakeRuntimeBackend()
    backend.values["indicator-style-overrides"] = {
        "BigGnome": "dot",
        "G-Unity": "hybrid",
    }
    runtime = RuntimeSettings(backend)

    serialized = runtime.serialized_overrides_without_layout("BigGnome")

    assert "BigGnome" not in serialized["indicator-style-overrides"]
    assert "G-Unity" in serialized["indicator-style-overrides"]


def test_compatibility_adapter_imports_active_layout_once():
    settings = settings_fixture()
    settings.active_layout = "BigGnome"

    settings._import_active_layout_once()
    first_values = dict(settings.runtime.values)
    settings.dock.values["background-opacity"] = 0.15
    settings._import_active_layout_once()

    assert settings.runtime.active_layout == "BigGnome"
    assert settings.runtime.imported == {"BigGnome"}
    assert first_values[("BigGnome", "dock-opacity")] == 77
    assert settings.runtime.values == first_values


def test_compatibility_adapter_imports_all_legacy_dock_settings_once():
    settings = settings_fixture()
    settings.active_layout = "BigGnome"
    settings.dock.values["background-opacity"] = 0.44
    settings.dock.values["dash-max-icon-size"] = 52
    settings.dock.values["intellihide"] = False
    settings.panel.values["indicator-style"] = "hybrid"
    settings.panel.values["dock-hover-effect"] = "lift"

    settings._import_active_layout_once()
    settings.dock.values["background-opacity"] = 0.12
    settings._import_active_layout_once()

    assert settings.runtime.values[("BigGnome", "dock-opacity")] == 44
    assert settings.runtime.values[("BigGnome", "dock-size")] == 52
    assert settings.runtime.values[("BigGnome", "dock-visibility")] == "always-hidden"
    assert settings.runtime.values[("BigGnome", "indicator-style")] == "hybrid"
    assert settings.runtime.values[("BigGnome", "dock-hover")] == "lift"


def test_compatibility_adapter_does_not_import_classic_indicator():
    settings = settings_fixture()
    settings.active_layout = "Classic"
    settings.dock_active = False
    settings.community_panel_active = True

    settings._import_active_layout_once()

    assert ("Classic", "indicator-style") not in settings.runtime.values


def test_compatibility_adapter_imports_legacy_taskbar_visibility_once():
    settings = settings_fixture()
    settings.active_layout = "Hybrid"
    settings.dock_active = False
    settings.community_panel_active = True
    settings.community_panel.values["intellihide"] = True
    settings.community_panel.values["intellihide-hide-from-windows"] = False

    settings._import_active_layout_once()
    settings.community_panel.values["intellihide-hide-from-windows"] = True
    settings._import_active_layout_once()

    assert settings.runtime.values[("Hybrid", "panel-visibility")] == "always-hidden"


def test_compatibility_adapter_imports_legacy_taskbar_opacity_once():
    settings = settings_fixture()
    settings.active_layout = "Hybrid"
    settings.dock_active = False
    settings.community_panel_active = True
    settings.community_panel.values["trans-panel-opacity"] = 0.46

    settings._import_active_layout_once()
    settings.community_panel.values["trans-panel-opacity"] = 0.52
    settings._import_active_layout_once()

    assert settings.runtime.values[("Hybrid", "panel-opacity")] == 46


def test_compatibility_adapter_imports_legacy_taskbar_height_once():
    settings = settings_fixture()
    settings.active_layout = "Hybrid"
    settings.dock_active = False
    settings.community_panel_active = True
    settings.community_panel.values["panel-sizes"] = '{"0":46}'

    settings._import_active_layout_once()
    settings.community_panel.values["panel-sizes"] = '{"0":52}'
    settings._import_active_layout_once()

    assert settings.runtime.values[("Hybrid", "panel-height")] == 46


@pytest.mark.parametrize(
    ("layout", "dock_active", "taskbar_active"),
    [
        ("BigGnome", True, False),
        ("G-Unity", True, False),
        ("Hybrid", False, True),
        ("Desk UX", False, True),
        ("Classic", False, True),
        ("Minimal", False, False),
    ],
)
def test_active_runtime_profiles_never_import_legacy_component_settings(
    layout,
    dock_active,
    taskbar_active,
):
    settings = settings_fixture()
    settings.active_layout = layout
    settings.dock_active = dock_active
    settings.community_panel_active = taskbar_active
    settings.runtime_active = True
    settings.panel.values["indicator-style"] = "dot"
    settings.community_panel.values["dot-style-focused"] = "DOTS"

    settings._import_active_layout_once()

    assert settings.runtime.active_layout == layout
    assert settings.runtime.imported == {layout}
    assert settings.runtime.values == {}


def test_live_writes_are_mirrored_to_layout_owned_runtime_settings():
    settings = settings_fixture()
    settings.active_layout = "Desk UX"

    settings.set_indicator_style("desk-ux")
    settings.set_panel_opacity(54)

    assert settings.runtime.values[("Desk UX", "indicator-style")] == "desk-ux"
    assert settings.runtime.values[("Desk UX", "panel-opacity")] == 54


def test_biggnome_menu_side_is_runtime_owned_and_validated():
    settings = settings_fixture()
    settings.active_layout = "BigGnome"
    settings.runtime_active = True

    settings.set_dock_menu_side("left")

    assert settings.dock_menu_side() == "left"
    assert settings.runtime.values[("BigGnome", "dock-menu-side")] == "left"
    with pytest.raises(ValueError):
        settings.set_dock_menu_side("center")


@pytest.mark.parametrize(
    ("layout", "expected"),
    [
        ("BigGnome", False),
        ("G-Unity", False),
        ("Hybrid", True),
        ("Desk UX", True),
        ("Classic", True),
        ("Minimal", False),
    ],
)
def test_startup_overview_defaults_and_overrides(layout, expected):
    settings = settings_fixture()
    settings.active_layout = layout
    settings.runtime_active = True

    assert settings.skip_startup_overview() is expected
    settings.set_skip_startup_overview(not expected)
    assert settings.skip_startup_overview() is not expected


def test_restore_defaults_updates_active_components_without_saving_overrides():
    settings = settings_fixture()
    settings.active_layout = "Hybrid"
    settings.dock_active = False
    settings.community_panel_active = True
    settings.runtime.values[("Hybrid", "panel-opacity")] = 45
    settings.runtime.values[("Hybrid", "panel-height")] = 52

    settings.restore_layout_defaults()

    assert settings.panel_opacity() == 70
    assert settings.panel_height() == 38
    assert settings.indicator_style() == "hybrid"
    assert not any(layout == "Hybrid" for layout, _setting in settings.runtime.values)


@pytest.mark.parametrize(
    ("layout", "dock_active", "taskbar_active", "expected"),
    [
        ("BigGnome", True, False, "desk-ux"),
        ("Desk UX", False, True, "desk-ux"),
        ("Hybrid", False, True, "hybrid"),
        ("G-Unity", True, False, "dot"),
    ],
)
def test_restore_uses_each_layout_indicator_contract(
    layout,
    dock_active,
    taskbar_active,
    expected,
):
    settings = settings_fixture()
    settings.active_layout = layout
    settings.dock_active = dock_active
    settings.community_panel_active = taskbar_active
    settings.runtime.values[(layout, "indicator-style")] = "hybrid"

    settings.restore_layout_defaults()

    assert settings.indicator_style() == expected
    assert (layout, "indicator-style") not in settings.runtime.values


def test_classic_restore_does_not_reenable_running_indicators():
    settings = settings_fixture()
    settings.active_layout = "Classic"
    settings.dock_active = False
    settings.community_panel_active = True
    settings.community_panel.values["dot-size"] = 0

    settings.restore_layout_defaults()

    assert settings.community_panel.values["dot-size"] == 0


def test_runtime_schema_declares_typed_per_layout_overrides():
    schema = (
        ROOT
        / "usr/share/glib-2.0/schemas/org.communitybig.layout-switcher.runtime.gschema.xml"
    ).read_text()

    assert 'id="org.communitybig.layout-switcher.runtime"' in schema
    assert 'name="dock-opacity-overrides" type="a{su}"' in schema
    assert 'name="panel-height-overrides" type="a{su}"' in schema
    assert 'name="dock-hover-overrides" type="a{ss}"' in schema
    assert 'name="dock-magnification-overrides" type="a{su}"' in schema
    assert 'name="dock-menu-side-overrides" type="a{ss}"' in schema
    assert 'name="skip-startup-overview-overrides" type="a{sb}"' in schema


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


def test_dock_size_is_clamped_and_mirrored_per_layout():
    settings = settings_fixture()
    settings.active_layout = "BigGnome"

    settings.set_dock_size(90)

    assert settings.dock_size() == 64
    assert settings.runtime.values[("BigGnome", "dock-size")] == 64


def test_dock_hover_effect_is_validated_and_mirrored_per_layout():
    settings = settings_fixture()
    settings.active_layout = "G-Unity"

    settings.set_dock_hover_effect("lift")

    assert settings.dock_hover_effect() == "lift"
    assert settings.runtime.values[("G-Unity", "dock-hover")] == "lift"


def test_dock_magnification_is_clamped_and_owned_per_dock_layout():
    settings = settings_fixture()
    settings.active_layout = "BigGnome"
    settings.runtime_active = True

    settings.set_dock_magnification(90)

    assert settings.dock_magnification() == 60
    assert settings.runtime.values[("BigGnome", "dock-magnification")] == 60


def test_taskbar_rejects_dock_magnification():
    settings = settings_fixture()
    settings.active_layout = "Hybrid"
    settings.dock_active = False
    settings.community_panel_active = True
    settings.runtime_active = True

    with pytest.raises(ValueError, match="unified Dock runtime"):
        settings.set_dock_hover_effect("magnify")


def test_unified_dock_settings_write_only_layout_owned_overrides():
    settings = settings_fixture()
    settings.active_layout = "BigGnome"
    settings.runtime_active = True
    legacy_dock = dict(settings.dock.values)
    legacy_panel = dict(settings.panel.values)

    settings.set_dock_opacity(42)
    settings.set_dock_size(90)
    settings.set_dock_visibility("always-visible")
    settings.set_dock_hover_effect("lift")
    settings.set_indicator_style("hybrid")

    assert settings.dock_opacity() == 42
    assert settings.dock_size() == 64
    assert settings.dock_visibility() == "always-visible"
    assert settings.dock_hover_effect() == "lift"
    assert settings.indicator_style() == "hybrid"
    assert settings.runtime.values[("BigGnome", "dock-opacity")] == 42
    assert settings.runtime.values[("BigGnome", "dock-size")] == 64
    assert settings.runtime.values[("BigGnome", "dock-visibility")] == "always-visible"
    assert settings.runtime.values[("BigGnome", "dock-hover")] == "lift"
    assert settings.runtime.values[("BigGnome", "indicator-style")] == "hybrid"
    assert settings.dock.values == legacy_dock
    assert settings.panel.values == legacy_panel


def test_taskbar_hover_effect_uses_the_same_curated_lift_profile():
    settings = settings_fixture()
    settings.active_layout = "Desk UX"
    settings.dock_active = False
    settings.community_panel_active = True

    settings.set_dock_hover_effect("lift")

    assert settings.dock_hover_effect() == "lift"
    assert settings.community_panel.values["animate-appicon-hover"] is True
    assert settings.community_panel.values["animate-appicon-hover-animation-type"] == "SIMPLE"
    assert (
        settings.community_panel.values["animate-appicon-hover-animation-duration"][
            "SIMPLE"
        ]
        == 220
    )
    assert (
        settings.community_panel.values["animate-appicon-hover-animation-travel"][
            "SIMPLE"
        ]
        == 0.08
    )
    assert (
        settings.community_panel.values["animate-appicon-hover-animation-zoom"]["SIMPLE"]
        == 1.08
    )
    assert settings.runtime.values[("Desk UX", "dock-hover")] == "lift"


def test_unified_taskbar_indicator_and_hover_are_layout_owned_only():
    settings = settings_fixture()
    settings.active_layout = "Desk UX"
    settings.dock_active = False
    settings.community_panel_active = True
    settings.runtime_active = True
    legacy_values = dict(settings.community_panel.values)

    settings.set_indicator_style("hybrid")
    settings.set_dock_hover_effect("lift")

    assert settings.indicator_style() == "hybrid"
    assert settings.dock_hover_effect() == "lift"
    assert settings.runtime.values[("Desk UX", "indicator-style")] == "hybrid"
    assert settings.runtime.values[("Desk UX", "dock-hover")] == "lift"
    assert settings.community_panel.values == legacy_values
    assert settings.community_panel.calls == []


def test_panel_settings_clamp_opacity_and_validate_visibility():
    settings = settings_fixture()

    settings.set_panel_opacity(130)
    settings.set_panel_visibility("intelligent")

    assert settings.panel_opacity() == 100
    assert settings.panel_visibility() == "intelligent"


def test_standalone_taskbar_opacity_keeps_compatibility_mirror():
    settings = settings_fixture()
    settings.community_panel_active = True

    settings.set_panel_opacity(43)

    assert settings.panel_opacity() == 43
    assert settings.community_panel.values["trans-use-custom-opacity"] is True
    assert settings.community_panel.values["trans-use-dynamic-opacity"] is False


def test_taskbar_opacity_writes_only_layout_owned_settings():
    settings = settings_fixture()
    settings.active_layout = "Hybrid"
    settings.community_panel_active = True
    settings.runtime_active = True
    legacy_values = dict(settings.community_panel.values)

    settings.set_panel_opacity(43)

    assert settings.panel_opacity() == 43
    assert settings.runtime.values[("Hybrid", "panel-opacity")] == 43
    assert settings.community_panel.values == legacy_values
    assert settings.community_panel.calls == []

    settings.runtime.values[("Hybrid", "panel-opacity")] = 130
    assert settings.panel_opacity() == 100


def test_minimal_opacity_writes_only_layout_owned_settings():
    settings = settings_fixture()
    settings.active_layout = "Minimal"
    settings.dock_active = False
    settings.community_panel_active = False
    settings.runtime_active = True
    legacy_values = dict(settings.panel.values)

    settings.set_panel_opacity(42)

    assert settings.panel_opacity() == 42
    assert settings.runtime.values[("Minimal", "panel-opacity")] == 42
    assert settings.panel.values == legacy_values
    assert settings.panel.calls == []


def test_minimal_restore_changes_only_runtime_owned_settings():
    settings = settings_fixture()
    settings.active_layout = "Minimal"
    settings.dock_active = False
    settings.community_panel_active = False
    settings.runtime_active = True
    settings.runtime.values[("Minimal", "panel-opacity")] = 42
    legacy_panel_values = dict(settings.panel.values)

    settings.restore_layout_defaults()

    assert settings.panel_opacity() == 65
    assert settings.runtime.values == {}
    assert settings.panel.values == legacy_panel_values
    assert settings.panel.calls == []


def test_taskbar_visibility_writes_only_layout_owned_settings():
    settings = settings_fixture()
    settings.active_layout = "Hybrid"
    settings.community_panel_active = True
    settings.runtime_active = True
    legacy_values = dict(settings.community_panel.values)

    settings.set_panel_visibility("always-visible")
    assert settings.panel_visibility() == "always-visible"

    settings.set_panel_visibility("always-hidden")
    assert settings.panel_visibility() == "always-hidden"

    settings.set_panel_visibility("intelligent")
    assert settings.panel_visibility() == "intelligent"
    assert settings.runtime.values[("Hybrid", "panel-visibility")] == "intelligent"
    assert settings.community_panel.values == legacy_values
    assert settings.community_panel.calls == []


def test_standalone_taskbar_visibility_keeps_compatibility_mirror():
    settings = settings_fixture()
    settings.active_layout = "Hybrid"
    settings.community_panel_active = True

    settings.set_panel_visibility("always-hidden")

    assert settings.runtime.values[("Hybrid", "panel-visibility")] == "always-hidden"
    assert settings.community_panel.values["intellihide"] is True
    assert settings.community_panel.values["intellihide-hide-from-windows"] is False


def test_taskbar_height_writes_only_layout_owned_settings():
    settings = settings_fixture()
    settings.active_layout = "Hybrid"
    settings.community_panel_active = True
    settings.runtime_active = True
    legacy_values = dict(settings.community_panel.values)

    settings.set_panel_height(18)

    assert settings.panel_height() == 32
    assert settings.runtime.values[("Hybrid", "panel-height")] == 32
    assert settings.community_panel.values == legacy_values
    assert settings.community_panel.calls == []

    settings.runtime.values[("Hybrid", "panel-height")] = 100
    assert settings.panel_height() == 56


def test_standalone_taskbar_height_preserves_monitor_map_and_clamps():
    settings = settings_fixture()
    settings.active_layout = "Hybrid"
    settings.community_panel_active = True
    settings.community_panel.values["panel-sizes"] = '{"0":38,"1":40}'

    settings.set_panel_height(18)

    assert settings.panel_height() == 32
    assert settings.community_panel.values["panel-sizes"] == '{"0":32,"1":32}'
    assert settings.runtime.values[("Hybrid", "panel-height")] == 32


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


def test_minimal_keeps_session_controls_reachable():
    window = (ROOT / "usr/share/layout-switcher/ui/window.py").read_text()
    layouts = (ROOT / "usr/share/layout-switcher/ui/page_layouts.py").read_text()

    assert "def refresh_layout_capabilities(self)" in window
    assert "panel_dock_row.set_sensitive(True)" in window
    assert 'panel_dock_page = self._pages.get("panel-dock")' in window
    assert "panel_dock_page.refresh()" in window
    assert layouts.count("root.refresh_layout_capabilities()") == 2


def test_panel_controls_refresh_after_extension_state_settles():
    window = (ROOT / "usr/share/layout-switcher/ui/window.py").read_text()

    assert 'panel_dock_page = self._pages.get("panel-dock")' in window
    assert "panel_dock_page.refresh()" in window


def test_first_upgrade_keeps_restart_action_visible():
    layouts = (ROOT / "usr/share/layout-switcher/ui/page_layouts.py").read_text()

    assert 'getattr(LayoutApplier, "last_apply_staged", False)' in layouts
    assert "timeout=0 if staged else 20" in layouts
    assert "restart_toast.set_priority(Adw.ToastPriority.HIGH)" in layouts


def test_page_exposes_opacity_and_visibility_controls():
    page = (ROOT / "usr/share/layout-switcher/ui/page_panel_dock.py").read_text()

    assert 'tr("Dock transparency")' in page
    assert 'tr("Dock size")' in page
    assert 'tr("Icon hover effect")' in page
    assert 'tr("Standard")' in page
    assert 'tr("Gentle lift")' in page
    assert 'tr("Magnification")' in page
    assert 'tr("Magnification intensity")' in page
    assert 'tr("Choose how much nearby Dock icons grow.")' in page
    assert 'tr("Choose how dock icons react to the pointer.")' in page
    assert "_build_hover_effect_button" in page
    assert 'tr("Panel transparency")' in page
    assert 'tr("Panel height")' in page
    assert 'tr("Restore layout defaults")' in page
    assert 'tr("Reset appearance and session options for the active layout.")' in page
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
    assert 'RUNTIME_UUID = "layout-switcher-runtime@communitybig.org"' in page
    assert 'RUNTIME_DOCK_LAYOUTS = frozenset(("BigGnome", "G-Unity"))' in page
    assert 'RUNTIME_TASKBAR_LAYOUTS = frozenset(("Hybrid", "Desk UX", "Classic"))' in page
    assert "runtime_active = ExtMgr.is_enabled(RUNTIME_UUID)" in page
    assert "runtime_active=runtime_active" in page
    assert "dock_available" in page
    assert "panel_available" in page
    assert "indicator_available" in page
    assert 'active_layout = Settings().get("active_layout", "")' in page
    assert 'active_layout != "Classic" and (dock_available or indicator_available)' in page
    assert 'tr("Taskbar")' in page
    assert 'tr("Configure running application indicators.")' in page
    assert "self._dock_opacity.set_visible(not community_panel_active)" in page
    assert 'tr("Configure the Community Panel appearance and visibility.")' in page
    assert 'tr("Application menu position")' in page
    assert 'tr("Place the BigGnome menu at either end of the Dock.")' in page
    assert "_build_menu_side_button" in page
    assert 'preview.add_css_class("dock-hover-preview")' in page
    assert "preview.set_halign(Gtk.Align.CENTER)" in page
    assert 'icon.add_css_class("dock-hover-preview-icon")' in page
    assert "menu.set_valign(Gtk.Align.END)" in page
    assert page.count("icon.set_valign(Gtk.Align.END)") == 2
    assert 'if value == "left":' in page
    assert 'if value == "right":' in page
    assert 'active_layout == "BigGnome"' in page
    assert 'tr("Open desktop after login")' in page
    assert 'tr("Skip the initial Activities overview for this layout.")' in page
    assert "set_skip_startup_overview" in page
    assert 'active_layout == "Minimal"' in page
    assert "native_panel_opacity_available" in page
    assert "panel_available and not native_panel_opacity_available" in page


def test_magnification_ui_is_translated_for_all_app_locales():
    messages = (
        "Magnification",
        "Magnification intensity",
        "Choose how much nearby Dock icons grow.",
    )
    localedir = ROOT / "usr/share/locale"

    for locale in APP_LOCALES:
        catalog = gettext.translation("layout-switcher", localedir, [locale])
        for message in messages:
            translated = catalog.gettext(message)
            assert translated
            if locale != "en":
                assert translated != message


def test_runtime_leaves_dock_fullscreen_tracking_to_native_engine():
    controller = (
        ROOT
        / "usr/share/gnome-shell/extensions/"
        "layout-switcher-runtime@communitybig.org/dockPanelController.js"
    ).read_text()

    native_dock = (
        ROOT
        / "usr/share/gnome-shell/extensions/"
        "layout-switcher-runtime@communitybig.org/dockSurface.js"
    ).read_text()

    assert "this._panelActorData.affectsStruts = overlayMode" in controller
    assert "this._panelActorData.trackFullscreen = overlayMode" in controller
    assert "this._dockActorData" not in controller
    assert "this._syncDockTracking" not in controller
    assert "this._restoreDockTracking" not in controller
    assert "this._applyDockFullscreen" not in controller
    assert "this._dockFullscreenState" not in controller
    assert "'notify::fullscreen'" in controller
    assert "Meta.LaterType.BEFORE_REDRAW" not in controller
    assert "Main.layoutManager._updateVisibility?.()" not in controller
    assert "'in-fullscreen-changed'" in controller
    assert "const monitorFullscreen = Boolean(" in controller
    assert "this._watchFullscreenSurface(actor);" in controller
    assert "this._watchFullscreenWindowActor(actor);" in controller
    assert "this._ensureFullscreenSurface();" in controller
    assert "surface.set_position(0, 0);" in controller
    assert "fullscreenSurfaceRepairCount" in controller
    assert "trackFullscreen: true" in native_dock
    assert "'in-fullscreen-changed'" in native_dock
