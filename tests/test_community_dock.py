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
        "docking.js": "254f217b6591cb08ada3729aa95d047f698831bcc29ddd5261f565e44ace8d2f",
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
        "background-opacity=0.70000000000000007",
        "max-alpha=0.70000000000000007",
        "click-action='minimize-or-previews'",
        "multi-monitor=true",
        "scroll-action='switch-workspace'",
        "show-mounts=false",
    ):
        assert setting in dock

    panel = layout.split("[org/communitybig/panel-and-dock]", 1)[1].split("\n\n", 1)[0]
    assert "panel-opacity=uint32 70" in panel


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


def test_legacy_dock_runtime_services_are_not_packaged():
    assert not (DOCK / "indicatorController.js").exists()
    assert not (DOCK / "notificationsMonitor.js").exists()


def test_dormant_optional_dock_services_are_not_packaged():
    docking = (DOCK / "docking.js").read_text()
    app_icons = (DOCK / "appIcons.js").read_text()
    dash = (DOCK / "dash.js").read_text()
    imports = (DOCK / "imports.js").read_text()

    assert not (DOCK / "appSpread.js").exists()
    assert "AppSpread" not in imports
    assert "KeyboardShortcuts" not in docking
    assert "WorkspaceIsolation" not in docking
    assert "appSpread" not in app_icons
    assert "isolateWorkspaces" not in app_icons
    assert "isolateMonitors" not in app_icons
    assert "isolateWorkspaces" not in dash
    assert "isolateMonitors" not in dash
    assert "buttonAction = clickAction.FOCUS_OR_PREVIEWS" in app_icons
    assert "buttonAction = clickAction.FOCUS_MINIMIZE_OR_PREVIEWS" in app_icons


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
    runtime = ROOT / "usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org"
    dock_runtime = (runtime / "dockRuntime.js").read_text()
    controller = (runtime / "dockPanelController.js").read_text()
    schema = (DOCK / "schemas/org.communitybig.panel-and-dock.gschema.xml").read_text()

    assert "Layout Switcher panel controller is required" in extension
    assert "this._extension.createPanelController()" in extension
    assert "this._host.createPanelController = () => new PanelController(" in dock_runtime
    assert "() => this._engine.docks" in dock_runtime
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
    assert "this._applyDockFullscreen(" not in controller
    assert "this._dockFullscreenState" not in controller
    assert "'notify::fullscreen'" not in controller
    assert "fullscreen: Boolean(monitor?.inFullscreen)" in controller
    assert "panel: this._engine.panelController?.diagnostics()" in dock_runtime
    assert "Main.layoutManager._findActor(this._panelBox)" in controller
    assert "this._panelActorData.affectsStruts = overlayMode" in controller
    assert "this._panelActorData.trackFullscreen = overlayMode" in controller
    assert "Main.layoutManager._findActor(dock)" in controller
    assert "this._dockActorData" not in controller
    assert "this._syncDockTracking" not in controller
    assert "this._restoreDockTracking" not in controller
    assert "Main.layoutManager._updateVisibility?.()" not in controller
    assert "'in-fullscreen-changed'" in controller
    assert "Main.layoutManager._queueUpdateRegions()" in controller
    assert "this._connect(Main.overview, 'shown'" in controller
    assert "this._connect(Main.overview, 'hiding'" in controller
    assert "this._connect(global.workspace_manager, 'active-workspace-changed'" in controller
    assert "this._connect(Main.layoutManager, 'monitors-changed'" in controller
    assert "Meta.LaterType.BEFORE_REDRAW" not in controller
    assert "this._queueVisibilityApply()" not in controller
    assert "windowFullscreen: Boolean(window?.fullscreen)" in controller
    assert "monitorFullscreen: Boolean(monitor?.inFullscreen)" in controller
    assert "windowActor: this._windowActorDiagnostics(windowActor)" in controller
    assert "translationX: Math.round(actor.translation_x)" in controller
    assert "transformedX: Math.round(transformedX)" in controller
    assert "transitions: transitionNames.filter" in controller
    assert "resizePending: Boolean(Main.wm?._resizePending?.has(actor))" in controller
    assert "resizing: Boolean(Main.wm?._resizing?.has(actor))" in controller
    assert "const monitorFullscreen = Boolean(" in controller
    assert "FULLSCREEN_EXIT_SETTLE_MS = 120" in controller
    assert "FULLSCREEN_REPAIR_STAGE_TIMEOUT_MS = 500" in controller
    assert "FULLSCREEN_EXIT_REPAIR_LIMIT = 3" in controller
    assert "() => this._onFullscreenChanged()" in controller
    assert "this._queueFullscreenExitRepair();" in controller
    assert "window.maximized_horizontally" in controller
    assert "const target = normal.maximized ? workArea : normal.frame" in controller
    assert "const targetBuffer = normal.maximized ? workArea : normal.buffer" in controller
    assert "const actorMatches = !actor" in controller
    assert "window.unmaximize();" in controller
    assert "window.maximize();" in controller
    assert "window.move_resize_frame(" in controller
    assert "'await-temporary-maximized'" in controller
    assert "'await-restored-normal'" in controller
    assert "this._rememberNormalGeometry();" in controller
    assert controller.index("window.unmaximize();") < controller.index(
        "window.maximize();"
    )
    assert controller.count("this._queueOpacityApply()") == 4
    assert "GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE" in controller
    assert "this._cancelOpacityApply();" in controller


def test_legacy_dock_panel_controller_is_not_packaged():
    assert not (DOCK / "panelController.js").exists()
