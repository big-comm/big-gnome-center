# SPDX-License-Identifier: MIT
"""Community Dock packaging and migration contracts."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCK = ROOT / "usr/share/gnome-shell/extensions/community-dock@communitybig.org"


def test_community_dock_has_distinct_identity_and_shell_support():
    metadata = json.loads((DOCK / "metadata.json").read_text())

    assert metadata["uuid"] == "community-dock@communitybig.org"
    assert metadata["name"] == "Community Dock"
    assert {"50", "51"}.issubset(metadata["shell-version"])
    assert metadata["original-author"] == "micxgx@gmail.com"


def test_community_dock_tracks_accepted_core_baseline():
    expected = {
        "docking.js": "99e214fc15e4b549b28fdaf2819d174012aa1c39f48b406e534445cb4db8e4dd",
    }

    for name, digest in expected.items():
        assert hashlib.sha256((DOCK / name).read_bytes()).hexdigest() == digest


def test_community_dock_preserves_license_provenance_and_schema():
    copying = (DOCK / "COPYING").read_text()
    upstream = (DOCK / "UPSTREAM.md").read_text()
    schema = (DOCK / "schemas/org.gnome.shell.extensions.dash-to-dock.gschema.xml").read_text()

    assert "GNU GENERAL PUBLIC LICENSE" in copying
    assert "Dash to Dock 106" in upstream
    assert "GPL-2.0-or-later" in upstream
    assert 'id="org.gnome.shell.extensions.dash-to-dock"' in schema


def test_layouts_do_not_reference_external_dash_to_dock():
    for path in (ROOT / "usr/share/layout-switcher/layouts").glob("*.txt"):
        layout = path.read_text()
        shell_section = layout.split("[org/gnome/shell]", 1)[1].split("\n\n", 1)[0]
        assert "dash-to-dock@micxgx.gmail.com" not in shell_section


def test_dock_layouts_use_only_unified_runtime():
    for filename in ("biggnome.txt", "g-unity.txt"):
        layout = (ROOT / f"usr/share/layout-switcher/layouts/{filename}").read_text()
        shell_section = layout.split("[org/gnome/shell]", 1)[1].split("\n\n", 1)[0]
        enabled_line = next(
            line for line in shell_section.splitlines() if line.startswith("enabled-extensions=")
        )

        assert "layout-switcher-runtime@communitybig.org" in enabled_line
        assert "community-dock@communitybig.org" not in enabled_line


def test_g_unity_preserves_its_left_fixed_dock_baseline():
    layout = (ROOT / "usr/share/layout-switcher/layouts/g-unity.txt").read_text()
    dock = layout.split("[org/gnome/shell/extensions/dash-to-dock]", 1)[1].split("\n\n", 1)[0]

    for setting in (
        "dock-position='LEFT'",
        "dock-fixed=true",
        "extend-height=true",
        "dash-max-icon-size=39",
        "background-opacity=0.80000000000000004",
        "click-action='minimize-or-previews'",
        "multi-monitor=true",
        "scroll-action='switch-workspace'",
        "show-mounts=false",
    ):
        assert setting in dock


def test_helper_and_applier_own_only_community_dock():
    helper = (
        ROOT / "usr/share/gnome-shell/extensions/"
        "layout-switcher-helper@communitybig.org/extension.js"
    ).read_text()
    applier = (ROOT / "usr/share/layout-switcher/layout_applier.py").read_text()

    assert "const COMMUNITY_DOCK_UUID = 'community-dock@communitybig.org'" in helper
    assert "_dockWillRun()" in helper
    assert "COMMUNITY_DOCK_UUID" in helper
    assert "dash-to-dock@micxgx.gmail.com" not in helper
    assert '_COMMUNITY_DOCK_UUID = "community-dock@communitybig.org"' in applier
    assert "_COMMUNITY_DOCK_UUID" in applier
    assert "dash-to-dock@micxgx.gmail.com" not in applier
    assert '_COMMUNITY_DOCK_UUID: "/org/gnome/shell/extensions/dash-to-dock/"' in applier


def test_package_compiles_dock_schema_and_installs_its_license():
    pkgbuild = (ROOT / "pkgbuild/PKGBUILD").read_text()

    assert (
        '"${pkgdir}/usr/share/gnome-shell/extensions/community-dock@communitybig.org/schemas"'
    ) in pkgbuild
    assert "community-dock-GPL-2.0.txt" in pkgbuild
    assert "'gnome-shell-extension-dash-to-dock'" not in pkgbuild


def test_running_indicator_styles_are_owned_by_community_dock():
    stylesheet = (DOCK / "stylesheet.css").read_text()
    controller = (DOCK / "indicatorController.js").read_text()
    extension = (DOCK / "extension.js").read_text()
    app_icons = (DOCK / "appIcons.js").read_text()

    assert "BigGnome parity is owned by Community Dock" in stylesheet
    assert "community-indicator-dot" in stylesheet
    assert "community-indicator-hybrid" in stylesheet
    assert "community-indicator-desk-ux" in stylesheet
    assert "width: 6px" in stylesheet
    assert "height: 3px" in stylesheet
    assert "width: 18px" in stylesheet
    assert "height: 4px" in stylesheet
    assert "rgba(160, 160, 168, 0.72)" in stylesheet
    assert "background-color: -st-accent-color" in stylesheet
    assert "layout-switcher-biggnome-dock" not in stylesheet
    assert "Layout Switcher indicator controller is required" in extension
    assert "new IndicatorController(this._extension, manager)" not in extension
    assert "changed::indicator-style" in controller
    assert "changed::running-indicator-style" in controller
    assert "this._dockSettings.set_enum('running-indicator-style', 0)" in controller
    assert "Per-icon ownership keeps style changes live" in stylesheet
    assert "COMMUNITY_INDICATOR_CLASSES" in app_icons
    assert "COMMUNITY_INDICATOR_GEOMETRY" in app_icons
    assert "changed::indicator-style" in app_icons
    assert "_syncCommunityIndicatorStyle()" in app_icons
    assert "_syncCommunityIndicatorAppearance()" in app_icons
    assert "this._dot.set_size(width, height)" in app_icons
    assert "background-color: ${color}" in app_icons
    assert "const isVertical = position === St.Side.LEFT || position === St.Side.RIGHT" in app_icons
    assert "[width, height] = [height, width]" in app_icons
    assert "? Clutter.ActorAlign.START" in app_icons
    assert "? Clutter.ActorAlign.END" in app_icons


def test_community_dock_focus_tracks_newly_focused_windows_immediately():
    app_icons = (DOCK / "appIcons.js").read_text()

    assert "global.display.focus_window" in app_icons
    assert "this.getWindows().includes(focusWindow)" in app_icons
    assert "global.display, 'notify::focus-window'" in app_icons
    assert "this._updateFocusState();" in app_icons


def test_community_dock_has_no_independent_settings_menu():
    app_icons = (DOCK / "appIcons.js").read_text()

    assert "Community Dock is configured exclusively by Layout Switcher." in app_icons
    assert "DockShowAppsIconMenu" not in app_icons
    assert "Docking.DockManager.extension.openPreferences()" not in app_icons
    assert "__('Dash to Dock')" not in app_icons


def test_community_dock_has_no_independent_preferences_ui():
    assert not (DOCK / "prefs.js").exists()
    assert not (DOCK / "Settings.ui").exists()


def test_community_dock_hover_effect_is_small_and_layout_switcher_owned():
    dash = (DOCK / "dash.js").read_text()
    schema = (DOCK / "schemas/org.communitybig.panel-and-dock.gschema.xml").read_text()

    assert 'name="dock-hover-effect" type="s"' in schema
    assert '<choice value="default"/>' in schema
    assert '<choice value="lift"/>' in schema
    assert "COMMUNITY_SETTINGS_SCHEMA" in dash
    assert "changed::dock-hover-effect" in dash
    assert "_animateAppIconHover" in dash
    assert "_syncHoverEffectStyle" in dash
    assert "community-dock-hover-lift" in dash
    assert "notify::hover" in dash
    assert "scale_x: lift ? 1.08 : 1" in dash


def test_community_dock_trash_refresh_stops_cleanly_during_runtime_reload():
    locations = (DOCK / "locations.js").read_text()
    refresh = locations.split("async _updateTrash()", 1)[1].split("launchAction", 1)[0]

    assert "if (e.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED))" in refresh
    assert "if (!this.location)" in refresh
    assert "const fallbackCancellable" in refresh
    assert "this._updateTrashCancellable === fallbackCancellable" in refresh
    assert "this._updateIconCancellable" not in refresh


def test_community_dock_owns_native_panel_runtime():
    extension = (DOCK / "extension.js").read_text()
    controller = (DOCK / "panelController.js").read_text()
    schema = (DOCK / "schemas/org.communitybig.panel-and-dock.gschema.xml").read_text()

    assert "new PanelController(this._extension)" in extension
    assert "this._panelController?.destroy()" in extension
    assert "Main.layoutManager.panelBox" in controller
    assert "panel-opacity" in controller
    assert "panel-visibility" in controller
    assert "always-visible" in schema
    assert "always-hidden" in schema
    assert "intelligent" in schema
    assert "indicator-style" in schema
    assert '<choice value="dot"/>' in schema
    assert '<choice value="hybrid"/>' in schema
    assert '<choice value="desk-ux"/>' in schema
    assert "addTopChrome" in controller
    assert "_pointerReveal" in controller
    assert "_panelInteractionActive()" in controller
    assert "manager?.activeMenu ?? manager?._activeMenu" in controller
    assert "global.stage.get_grab_actor()" in controller
    assert "this._panel.statusArea.quickSettings?.menu.actor.contains" in controller
    assert "!this._panel.hover && !this._panelInteractionActive()" in controller
    assert "Main.layoutManager.getWorkAreaForMonitor" in controller
    assert "window.maximized_vertically || window.fullscreen" in controller
    assert "Main.layoutManager._findActor(this._panelBox)" in controller
    assert "this._panelActorData.affectsStruts = overlayMode" in controller
    assert "Main.layoutManager._queueUpdateRegions()" in controller
