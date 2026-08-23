# SPDX-License-Identifier: MIT
"""Unified Shell runtime extraction contracts."""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_UUID = "layout-switcher-runtime@communitybig.org"
RUNTIME = ROOT / f"usr/share/gnome-shell/extensions/{RUNTIME_UUID}"
LAYOUTS = ROOT / "usr/share/layout-switcher/layouts"


def _enabled_extensions(layout_path: Path) -> list[str]:
    source = layout_path.read_text()
    shell = source.split("[org/gnome/shell]", 1)[1].split("\n\n", 1)[0]
    enabled = next(line for line in shell.splitlines() if line.startswith("enabled-extensions="))
    return ast.literal_eval(enabled.split("=", 1)[1])


def test_unified_runtime_has_distinct_identity_and_supported_shells():
    metadata = json.loads((RUNTIME / "metadata.json").read_text())

    assert metadata["uuid"] == RUNTIME_UUID
    assert metadata["name"] == "Layout Switcher Shell Runtime"
    assert {"50", "51"}.issubset(metadata["shell-version"])
    assert metadata["version"] == 2


def test_unified_runtime_is_modular_and_has_no_preferences_entry_point():
    extension = (RUNTIME / "extension.js").read_text()
    controller = (RUNTIME / "runtimeController.js").read_text()

    assert "new RuntimeController(this)" in extension
    assert "new DockRuntime(this._extension)" in controller
    assert "new TaskbarRuntime(this._extension)" in controller
    assert "org.communitybig.layout-switcher.runtime" in controller
    assert "PASSIVE_BUILD" not in controller
    assert not (RUNTIME / "prefs.js").exists()
    assert not (RUNTIME / "Settings.ui").exists()


def test_unified_runtime_profiles_capture_all_six_layout_surfaces():
    profiles = (RUNTIME / "layoutProfiles.js").read_text()

    for layout in ("BigGnome", "G-Unity", "Hybrid", "Desk UX", "Classic", "Minimal"):
        assert f"['{layout}'," in profiles
    assert "surface: RuntimeSurface.DOCK" in profiles
    assert "surface: RuntimeSurface.TASKBAR" in profiles
    assert "surface: RuntimeSurface.NATIVE" in profiles
    assert "indicator: 'none'" in profiles
    assert "labels: true" in profiles
    assert "['BigGnome', Object.freeze({" in profiles
    assert profiles.count("indicator: 'desk-ux'") == 2
    assert profiles.count("indicator: 'hybrid'") == 1
    assert profiles.count("indicator: 'dot'") == 1
    assert profiles.count("hover: 'lift'") == 1
    assert profiles.count("hover: 'default'") == 5


def test_unified_runtime_applies_profile_or_override_indicator_before_activation():
    controller = (RUNTIME / "runtimeController.js").read_text()
    dock = (RUNTIME / "dockRuntime.js").read_text()
    taskbar = (RUNTIME / "taskbarRuntime.js").read_text()

    assert "indicator-style-overrides" in controller
    assert "dock-hover-overrides" in controller
    assert "this._dock.activate(profile, indicator, hover)" in controller
    assert "this._taskbar.activate(profile, indicator, hover)" in controller
    assert "set_string('indicator-style', style)" in dock
    assert "set_string('dock-hover-effect', effect)" in dock
    assert "set_enum('dock-position', position)" in dock
    assert "dot: ['DOTS', 'DOTS', 6]" in taskbar
    assert "hybrid: ['SEGMENTED', 'SEGMENTED', 3]" in taskbar
    assert "'desk-ux': ['METRO', 'DASHES', 3]" in taskbar
    assert "settings.set_int('dot-size', 0)" in taskbar
    assert "settings.set_boolean('animate-appicon-hover', hover === 'lift')" in taskbar


def test_unified_runtime_replaces_component_extension_activation():
    for layout_path in LAYOUTS.glob("*.txt"):
        enabled = _enabled_extensions(layout_path)
        assert RUNTIME_UUID in enabled
        assert "community-dock@communitybig.org" not in enabled
        assert "community-panel@communitybig.org" not in enabled


def test_unified_runtime_loads_rollback_engines_behind_one_controller():
    dock = (RUNTIME / "dockRuntime.js").read_text()
    taskbar = (RUNTIME / "taskbarRuntime.js").read_text()

    assert "CommunityDockRuntime" in dock
    assert "CommunityPanelRuntime" in taskbar
    assert "ComponentHost" in dock
    assert "ComponentHost" in taskbar


def test_unified_runtime_preserves_helper_fault_isolation():
    metadata = json.loads((RUNTIME / "metadata.json").read_text())
    helper = ROOT / (
        "usr/share/gnome-shell/extensions/"
        "layout-switcher-helper@communitybig.org/metadata.json"
    )

    assert helper.is_file()
    assert json.loads(helper.read_text())["uuid"] != metadata["uuid"]
    assert "LayoutSwitcherHelper" not in (RUNTIME / "extension.js").read_text()
