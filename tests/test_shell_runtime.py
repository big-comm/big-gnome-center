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
    assert "RUNTIME_BUILD = 51" in controller
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
    assert "visibility: 'intelligent'" in profiles
    assert "visibility: 'always-visible'" in profiles
    assert "extended: false" in profiles
    assert "extended: true" in profiles


def test_unified_runtime_applies_profile_or_override_indicator_before_activation():
    controller = (RUNTIME / "runtimeController.js").read_text()
    dock = (RUNTIME / "dockRuntime.js").read_text()
    taskbar = (RUNTIME / "taskbarRuntime.js").read_text()

    assert "indicator-style-overrides" in controller
    assert "dock-hover-overrides" in controller
    assert "this._dock.activate(profile, indicator, hover, visibility)" in controller
    assert "this._taskbar.activate(profile, indicator, hover)" in controller
    assert "set_string('indicator-style', style)" in dock
    assert "set_string('dock-hover-effect', effect)" in dock
    assert "this._host.placement.apply(profile?.edge, profile?.extended)" in dock
    assert "dot: ['DOTS', 'DOTS', 6]" in taskbar
    assert "hybrid: ['SEGMENTED', 'SEGMENTED', 3]" in taskbar
    assert "'desk-ux': ['METRO', 'DASHES', 3]" in taskbar
    assert "settings.set_int('dot-size', 0)" in taskbar
    assert "settings.set_boolean('animate-appicon-hover', hover === 'lift')" in taskbar


def test_runtime_owns_dock_visibility_modes():
    controller = (RUNTIME / "runtimeController.js").read_text()
    runtime = (RUNTIME / "dockVisibilityModes.js").read_text()
    dock = (RUNTIME / "dockRuntime.js").read_text()
    engine = (
        ROOT
        / "usr/share/gnome-shell/extensions/"
        "layout-switcher-runtime@communitybig.org/dockSurface.js"
    ).read_text()

    assert "dock-visibility-overrides" in controller
    assert "new DockVisibilityModes(" in dock
    assert "this._host.visibilityModes.apply(visibility)" in dock
    for mode in ("always-visible", "always-hidden", "intelligent"):
        assert f"'{mode}'" in runtime
    assert "set_boolean('manualhide', false)" in runtime
    assert "set_boolean('dock-fixed', selected === 'always-visible')" in runtime
    assert "set_boolean('intellihide', selected === 'intelligent')" in runtime
    assert "set_boolean('autohide', selected !== 'always-visible')" in runtime
    assert "visibilityModes?.runtimeState()" in engine


def test_runtime_owns_accepted_dock_placement():
    runtime = (RUNTIME / "dockPlacement.js").read_text()
    dock = (RUNTIME / "dockRuntime.js").read_text()
    utils = (
        ROOT
        / "usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/dock/utils.js"
    ).read_text()

    assert "new DockPlacement(" in dock
    assert "['bottom', St.Side.BOTTOM]" in runtime
    assert "['left', St.Side.LEFT]" in runtime
    assert "set_enum('dock-position', position)" in runtime
    assert "set_boolean('extend-height', Boolean(extended))" in runtime
    assert "Clutter.TextDirection.RTL" in runtime
    assert "Docking.DockSurfaceManager.extension.placement" in utils


def test_unified_runtime_replaces_component_extension_activation():
    for layout_path in LAYOUTS.glob("*.txt"):
        enabled = _enabled_extensions(layout_path)
        assert RUNTIME_UUID in enabled
        assert "community-dock@communitybig.org" not in enabled
        assert "community-panel@communitybig.org" not in enabled


def test_unified_runtime_loads_rollback_engines_behind_one_controller():
    dock = (RUNTIME / "dockRuntime.js").read_text()
    taskbar = (RUNTIME / "taskbarRuntime.js").read_text()

    assert "CommunityDockRuntime" not in dock
    assert "import {DockSurfaceManager}" in dock
    assert "CommunityPanelRuntime" not in taskbar
    assert "new TaskbarSurfaceManager(this._host)" in taskbar
    assert "ComponentHost" in dock
    assert "ComponentHost" in taskbar


def test_taskbar_lifecycle_is_owned_by_the_unified_runtime():
    taskbar = (RUNTIME / "taskbarRuntime.js").read_text()
    surface = (RUNTIME / "taskbarSurface.js").read_text()
    adapter = (
        ROOT
        / "usr/share/gnome-shell/extensions/community-panel@communitybig.org/extension.js"
    ).read_text()
    context = (
        ROOT
        / "usr/share/gnome-shell/extensions/community-panel@communitybig.org/runtimeContext.js"
    ).read_text()

    assert "new TaskbarSurfaceManager(this._host)" in taskbar
    assert "await this._surface.enable()" in taskbar
    assert "this._surface.destroy()" in taskbar
    assert "new PanelManager.PanelManager()" in surface
    assert "manager.enable();" in surface
    assert "manager?.disable();" in surface
    assert "Context.initializeRuntimeContext(this._host, this)" in surface
    assert "Context.clearRuntimeContext(this);" in surface
    assert surface.index("manager?.disable();") < surface.index(
        "Context.clearRuntimeContext(this);"
    )
    assert "activationPending" in surface
    assert "globalOwned" in surface
    assert "TaskbarSurfaceManager" in adapter
    assert "PanelManager" not in adapter
    assert "initializeRuntimeContext" in context
    assert "clearRuntimeContext" in context


def test_inherited_taskbar_modules_use_the_separate_runtime_context():
    panel = ROOT / "usr/share/gnome-shell/extensions/community-panel@communitybig.org"
    consumers = [
        "appIcons.js",
        "intellihide.js",
        "notificationsMonitor.js",
        "overview.js",
        "panel.js",
        "panelManager.js",
        "panelStyle.js",
        "taskbar.js",
        "transparency.js",
        "windowPreview.js",
    ]

    for name in consumers:
        source = (panel / name).read_text()
        assert "from './extension.js'" not in source
        assert "from './runtimeContext.js'" in source


def test_dock_lifecycle_is_owned_by_the_unified_runtime():
    dock = (RUNTIME / "dockRuntime.js").read_text()

    assert "new DockSurfaceManager(this._host)" in dock
    assert "this._manager = manager" in dock
    assert "manager ?? DockSurfaceManager.getDefault()" in dock
    assert "partialManager?.destroy()" in dock
    assert "this._panelController?.destroy()" in dock
    assert "this._indicatorController?.destroy()" in dock
    assert "manager?.destroy()" in dock
    assert dock.index("this._panelController?.destroy()") < dock.index(
        "manager?.destroy()"
    )
    assert "CommunityDockRuntime" not in dock


def test_runtime_owns_dock_actor_construction():
    runtime = (RUNTIME / "dockRuntime.js").read_text()
    factory = (RUNTIME / "dockActorFactory.js").read_text()
    engine = (
        ROOT
        / "usr/share/gnome-shell/extensions/"
        "layout-switcher-runtime@communitybig.org/dockSurface.js"
    ).read_text()

    assert "new DockActorFactory()" in runtime
    assert "this._host.createDockActor" in runtime
    assert "export const DockedDash" in engine
    assert "this._extension.createDockActor(params)" in engine
    assert "const dock = new DockedDash(params)" not in engine
    assert "Layout Switcher Dock actor factory is required" in engine


def test_private_dock_modules_resolve_code_from_the_unified_runtime():
    host = (RUNTIME / "componentHost.js").read_text()
    dock = (RUNTIME / "dockRuntime.js").read_text()
    locations = (RUNTIME / "dock/locations.js").read_text()

    assert "this.codePath = codeDirectory" in host
    assert "}, 'dock');" in dock
    assert "DockSurfaceManager.extension.codePath" in locations
    assert "DockSurfaceManager.extension.path," not in locations


def test_component_stylesheets_unload_from_the_current_shell_theme():
    host = (RUNTIME / "componentHost.js").read_text()

    load = host.split("loadStylesheet()", 1)[1].split("unloadStylesheet()", 1)[0]
    unload = host.split("unloadStylesheet()", 1)[1]
    assert "this._stylesheets.push(file)" in load
    assert "this._stylesheets.push([theme, file])" not in load
    assert "const theme = St.ThemeContext.get_for_stage(global.stage).get_theme()" in unload
    assert "for (const file of this._stylesheets.splice(0))" in unload


def test_runtime_owns_native_panel_controller_for_dock_layouts():
    dock = (RUNTIME / "dockRuntime.js").read_text()
    controller = (RUNTIME / "dockPanelController.js").read_text()

    assert "this._host.createPanelController = () => new PanelController(" in dock
    assert "() => this._manager?._allDocks ?? []" in dock
    assert "Main.layoutManager.panelBox" in controller
    assert "this._applyDockFullscreen(" not in controller
    assert "this._dockActorData" not in controller
    assert "this._syncDockTracking" not in controller
    assert "'in-fullscreen-changed'" in controller
    assert "this._host.createPanelController()" in dock


def test_runtime_owns_the_accepted_primary_dock_app_actions():
    actions = (RUNTIME / "dockAppActions.js").read_text()
    dock = (RUNTIME / "dockRuntime.js").read_text()
    app_icons = (
        ROOT
        / "usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/dock/appIcons.js"
    ).read_text()

    assert "new DockAppActions()" in dock
    assert "appActions?.activate(this, button)" in app_icons
    assert "button !== PRIMARY_BUTTON || modifiers" in actions
    assert "app.open_new_window(-1)" in actions
    assert "Main.activateWindow(windows[0])" in actions
    assert "window.minimize()" in actions
    assert "icon._windowPreviews()" in actions
    assert "Main.overview.hide()" in actions


def test_runtime_owns_dock_favorites_and_running_app_order():
    model = (RUNTIME / "dockAppModel.js").read_text()
    dock = (RUNTIME / "dockRuntime.js").read_text()
    dash = (
        ROOT
        / "usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/dock/dash.js"
    ).read_text()

    assert "new DockAppModel()" in dock
    assert "appModel?.favorites()" in dash
    assert "appModel?.running()" in dash
    assert "appModel.order(" in dash
    assert "getFavoriteMap()" in model
    assert "get_running()" in model
    assert "const pending = [...running]" in model
    assert "pending.indexOf(oldApp)" in model
    assert "app.get_id() in favorites" in model


def test_runtime_owns_dock_notification_monitor_and_badge_count():
    monitor = (RUNTIME / "dockNotificationMonitor.js").read_text()
    dock = (RUNTIME / "dockRuntime.js").read_text()
    manager = (
        ROOT
        / "usr/share/gnome-shell/extensions/"
        "layout-switcher-runtime@communitybig.org/dockSurface.js"
    ).read_text()
    indicators = (
        ROOT
        / "usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/dock/appIconIndicators.js"
    ).read_text()

    assert "new DockNotificationMonitor(" in dock
    assert "this._host.notificationsMonitor" in dock
    assert "this._destroyNotificationsMonitor()" in dock
    assert "Signals:" in monitor
    assert "Main.messageTray.getSources()" in monitor
    assert "show-icons-notifications-counter" in monitor
    assert "notify::acknowledged" in monitor
    assert "getBadgeCount(" in monitor
    assert "this._notificationsMonitor = this._extension.notificationsMonitor" in manager
    assert "this._extension.notificationsMonitor ??" not in manager
    assert "this._ownsNotificationsMonitor" not in manager
    assert "notificationsMonitor.getBadgeCount" in indicators
    assert "notificationsMonitor.getAppNotificationsCount" in indicators


def test_runtime_owns_dock_notification_badge_actor_and_text():
    badges = (RUNTIME / "dockNotificationBadges.js").read_text()
    dock = (RUNTIME / "dockRuntime.js").read_text()
    indicators = (
        ROOT
        / "usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/dock/appIconIndicators.js"
    ).read_text()

    assert "new DockNotificationBadges()" in dock
    assert "textForCount(count)" in badges
    assert "new St.Bin" in badges
    assert "styleClass: 'notification-badge'" in badges
    assert "presenter.textForCount(count)" in indicators
    assert "presenter?.create(text)" in indicators
    assert "presenter.setText(this._notificationBadgeBin, text)" in indicators


def test_runtime_owns_dock_running_indicator_renderers():
    runtime = (RUNTIME / "dockRunningIndicators.js").read_text()
    dock = (RUNTIME / "dockRuntime.js").read_text()
    icons = (
        ROOT
        / "usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/dock/appIcons.js"
    ).read_text()

    assert "new DockRunningIndicators(" in dock
    assert "this._host.createIndicatorController" in dock
    assert "this._host.createIndicatorController(manager)" in dock
    assert "applyIconStyle(icon)" in runtime
    assert "applyAppearance(dot, focused, position)" in runtime
    assert "['dot', {inactive: [6, 6], active: [6, 6]" in runtime
    assert "['hybrid', {inactive: [18, 4], active: [18, 4]" in runtime
    assert "['desk-ux', {inactive: [8, 3], active: [18, 3]" in runtime
    assert "controller.applyIconStyle(this)" in icons
    assert "controller.applyAppearance(this._dot, this.focused, position)" in icons


def test_runtime_owns_dock_hover_effects():
    runtime = (RUNTIME / "dockHoverEffects.js").read_text()
    dock = (RUNTIME / "dockRuntime.js").read_text()
    dash = (
        ROOT
        / "usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/dock/dash.js"
    ).read_text()

    assert "new DockHoverEffects(" in dock
    assert "this._host.hoverEffects.setEffect(effect)" in dock
    assert "getSettings(PANEL_SCHEMA)" in dock
    assert "applyStyle(actor)" in runtime
    assert "animate(actor, position, iconSize)" in runtime
    assert "get_string('dock-hover-effect')" in runtime
    assert "scale_x: lift ? 1.08 : 1" in runtime
    assert "hoverEffects.animate(actor, this._position, this.iconSize)" in dash
    assert "hoverEffects.applyStyle(this)" in dash


def test_runtime_owns_core_dock_context_menu_actions():
    actions = (RUNTIME / "dockAppMenuActions.js").read_text()
    dock = (RUNTIME / "dockRuntime.js").read_text()
    app_icons = (
        ROOT
        / "usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/dock/appIcons.js"
    ).read_text()

    assert "new DockAppMenuActions()" in dock
    assert "appMenuActions?.activateWindow(window)" in app_icons
    assert "?.openNewWindow(this.sourceActor)" in app_icons
    assert "?.launchOnGpu(this.sourceActor, gpuPref)" in app_icons
    assert "?.launchDesktopAction(this.sourceActor" in app_icons
    assert "?.setFavorite(app.get_id(), false)" in app_icons
    assert "?.setFavorite(app.get_id(), true)" in app_icons
    assert "appMenuActions?.quit(this.sourceActor)" in app_icons
    assert "Main.activateWindow(window)" in actions
    assert "icon.app.open_new_window(-1)" in actions
    assert "favorites.addFavorite(appId)" in actions
    assert "favorites.removeFavorite(appId)" in actions
    assert "window.delete(time)" in actions


def test_runtime_owns_dock_context_menu_construction():
    runtime = (RUNTIME / "dockAppIconMenu.js").read_text()
    dock = (RUNTIME / "dockRuntime.js").read_text()
    app_icons = (
        ROOT
        / "usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/dock/appIcons.js"
    ).read_text()

    assert "class DockAppIconMenu extends PopupMenu.PopupMenu" in runtime
    assert "new DockAppMenuFactory()" in dock
    assert "appMenuFactory" in app_icons
    assert "?.create(this, this instanceof DockAppIcon)" in app_icons
    assert "new DockAppIconMenu(this)" in app_icons
    assert "this._isApplicationIcon" in runtime


def test_unified_runtime_preserves_helper_fault_isolation():
    metadata = json.loads((RUNTIME / "metadata.json").read_text())
    helper = ROOT / (
        "usr/share/gnome-shell/extensions/"
        "layout-switcher-helper@communitybig.org/metadata.json"
    )

    assert helper.is_file()
    assert json.loads(helper.read_text())["uuid"] != metadata["uuid"]
    assert "LayoutSwitcherHelper" not in (RUNTIME / "extension.js").read_text()
