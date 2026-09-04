# SPDX-License-Identifier: MIT
"""Unified Shell runtime extraction contracts."""

import ast
import gettext
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_UUID = "layout-switcher-runtime@communitybig.org"
RUNTIME = ROOT / f"usr/share/gnome-shell/extensions/{RUNTIME_UUID}"
LAYOUTS = ROOT / "usr/share/layout-switcher/layouts"
SUPPORTED_LOCALES = (
    "bg", "cs", "da", "de", "el", "en", "es", "et", "fi", "fr", "he", "hr",
    "hu", "is", "it", "ja", "ko", "nl", "no", "pl", "pt_BR", "pt", "ro", "ru",
    "sk", "sv", "tr", "uk", "zh",
)


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
    assert "RUNTIME_BUILD = 86" in controller
    assert not (RUNTIME / "prefs.js").exists()
    assert not (RUNTIME / "Settings.ui").exists()


def test_unified_runtime_owns_and_binds_surface_translations():
    extension = (RUNTIME / "extension.js").read_text()

    assert "this.initTranslations('dashtodock')" in extension
    assert "this.initTranslations('dash-to-panel')" in extension
    for domain in ("dashtodock", "dash-to-panel"):
        assert (RUNTIME / f"locale/pt_BR/LC_MESSAGES/{domain}.mo").is_file()

    dock = gettext.translation("dashtodock", RUNTIME / "locale", ["pt_BR"])
    assert dock.gettext("All Windows") == "Todas as janelas"
    assert dock.gettext("Pin to Dock") == "Fixar no dock"

    taskbar = gettext.translation("dash-to-panel", RUNTIME / "locale", ["pt_BR"])
    assert taskbar.gettext("Show Desktop") == "Exibir área de trabalho"


def test_unified_runtime_packages_all_supported_surface_catalogs():
    for domain in ("dashtodock", "dash-to-panel"):
        for locale in SUPPORTED_LOCALES:
            assert (RUNTIME / f"po/{domain}/{locale}.po").is_file()
            gettext.translation(domain, RUNTIME / "locale", [locale])


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
    assert "panelHeight: 38" in profiles
    assert "panelHeight: 40" in profiles
    assert profiles.count("panelOpacity: 70") == 2
    assert profiles.count("panelOpacity: 65") == 2
    assert "dockOpacity: 77" in profiles
    assert "dockOpacity: 70" in profiles
    assert profiles.count("dockSize: 39") == 2
    assert "extended: false" in profiles
    assert "extended: true" in profiles


def test_runtime_reports_bottom_surface_clearance_for_notifications():
    extension = (RUNTIME / "extension.js").read_text()
    controller = (RUNTIME / "runtimeController.js").read_text()
    dock = (RUNTIME / "dockRuntime.js").read_text()
    taskbar = (RUNTIME / "taskbarRuntime.js").read_text()

    assert "notificationBottomOffset(monitorIndex)" in extension
    assert "RuntimeSurface.DOCK" in controller
    assert "RuntimeSurface.TASKBAR" in controller
    assert "dock?.position !== 2" in dock
    assert "dock.height" in dock
    assert "panel?.geom?.position !== 2" in taskbar
    assert "panel.geom.outerSize" in taskbar


def test_gunity_dock_uses_shared_bigcommunity_menu_icon():
    dock = (RUNTIME / "dockRuntime.js").read_text()
    app_icons = (RUNTIME / "dock/appIcons.js").read_text()

    assert "this._host.layout = profile.layout" in dock
    assert "delete this._host.layout" in dock
    assert "Docking.DockSurfaceManager.extension.layout === 'G-Unity'" in app_icons
    assert "GUNITY_MENU_ICON_NAME = 'bigcommunity-menu-symbolic'" in app_icons
    assert "this._iconActor.gicon = null" in app_icons


def test_unified_runtime_applies_profile_or_override_indicator_before_activation():
    controller = (RUNTIME / "runtimeController.js").read_text()
    dock = (RUNTIME / "dockRuntime.js").read_text()
    taskbar = (RUNTIME / "taskbarRuntime.js").read_text()

    assert "indicator-style-overrides" in controller
    assert "dock-hover-overrides" in controller
    assert "dock-magnification-overrides" in controller
    assert "profile, indicator, hover, magnificationIntensity, dockOpacity" in controller
    assert "profile, indicator, hover, panelOpacity," in controller
    assert "panelVisibility, panelHeight);" in controller
    assert "this._host.runningIndicators?.setStyle(style)" in dock
    assert "this._host.hoverEffects.setEffect(effect, magnificationIntensity)" in dock
    assert "set_string('indicator-style', style)" not in dock
    assert "set_string('dock-hover-effect', effect)" not in dock
    assert "this._host.placement.apply(profile?.edge, profile?.extended)" in dock
    assert "dot: ['DOTS', 'DOTS', 6]" in taskbar
    assert "hybrid: ['SEGMENTED', 'SEGMENTED', 3]" in taskbar
    assert "'desk-ux': ['METRO', 'DASHES', 3]" in taskbar
    assert "settings.set_int('dot-size', 0)" in taskbar
    assert "settings.set_boolean('animate-appicon-hover', lift)" in taskbar
    assert "new GLib.Variant(variantType, values)" in taskbar


def test_native_profile_explicitly_releases_all_managed_surfaces():
    controller = (RUNTIME / "runtimeController.js").read_text()
    branch_start = controller.index(
        "profile.surface === RuntimeSurface.NATIVE")
    native = controller[branch_start:controller.index(
        "    _indicatorForProfile", branch_start)]

    assert "this._dock.deactivate();" in native
    assert "this._taskbar.deactivate();" in native
    assert "Unsupported runtime surface" in native


def test_runtime_listens_to_every_owned_visual_setting():
    controller = (RUNTIME / "runtimeController.js").read_text()

    for key in (
        "dock-hover-overrides",
        "dock-magnification-overrides",
        "dock-menu-side-overrides",
        "dock-opacity-overrides",
        "dock-size-overrides",
        "dock-visibility-overrides",
        "indicator-style-overrides",
        "panel-height-overrides",
        "panel-opacity-overrides",
        "panel-visibility-overrides",
        "skip-startup-overview-overrides",
    ):
        assert f"'{key}'," in controller
    assert "const dockProfileChanged" in controller
    assert "if (dockProfileChanged)" in controller


def test_runtime_owns_biggnome_menu_side_without_legacy_writes():
    controller = (RUNTIME / "runtimeController.js").read_text()
    dock = (RUNTIME / "dockRuntime.js").read_text()
    surface = (RUNTIME / "dockSurface.js").read_text()
    dash = (RUNTIME / "dock/dash.js").read_text()

    assert "_menuSideForProfile(profile)" in controller
    assert "profile.layout !== 'BigGnome'" in controller
    assert "this._applyMenuSide(menuSide)" in dock
    assert "this._manager?.updateMenuSide()" in dock
    assert "get menuAtStart()" in surface
    assert "dock.dash.updateShowAppsButton(true)" in surface
    assert "Docking.DockSurfaceManager.menuAtStart" in dash
    assert "updateShowAppsButton(force = false)" in dash
    assert "if (!force &&" in dash
    assert "const anchor = showAppsContainer === this._dashContainer" in dash
    assert "set_child_below_sibling(this._showAppsIcon, anchor)" in dash
    assert "set_child_above_sibling(this._showAppsIcon, anchor)" in dash
    assert "menuSide: Number.isFinite(menuX)" in dock
    assert "set_boolean('show-apps-at-top'" not in dock


def test_runtime_owns_startup_overview_for_every_surface():
    controller = (RUNTIME / "runtimeController.js").read_text()
    integration = (RUNTIME / "startupOverviewIntegration.js").read_text()
    dock_surface = (RUNTIME / "dockSurface.js").read_text()
    taskbar_surface = (RUNTIME / "taskbarSurface.js").read_text()

    assert "new StartupOverviewIntegration()" in controller
    assert "this._startupOverview.apply(skipStartupOverview)" in controller
    synchronous_apply = controller.index(
        "this._startupOverview.apply(\n            this._skipStartupOverviewForProfile(startupProfile))"
    )
    assert synchronous_apply < controller.index("this._queueSync();")
    assert "Main.sessionMode.hasOverview = value" in integration
    assert "Main.overview.hide()" in integration
    assert "layoutSwitcherStartupOverviewHandled" in integration
    assert "this._firstSessionActivation" in integration
    assert "'startup-complete'" in integration
    assert "implementation: 'layout-switcher-runtime'" in integration
    assert "restorationPending" in integration
    assert "restoreConflicts" in integration
    assert "postStartupHide" in integration
    assert "this._extension.skipStartupOverview" in dock_surface
    assert "disableOverviewOnStartup" not in dock_surface
    assert "hide-overview-on-startup" not in taskbar_surface
    assert "startInOverview" not in taskbar_surface


def test_runtime_owns_light_shell_popovers_except_for_minimal():
    controller = (RUNTIME / "runtimeController.js").read_text()
    integration = (RUNTIME / "shellPopoverThemeIntegration.js").read_text()
    stylesheet = (RUNTIME / "stylesheet.css").read_text()

    assert "new ShellPopoverThemeIntegration()" in controller
    assert "this._shellPopoverTheme.apply(profile.layout)" in controller
    assert "shellPopoverTheme: this._shellPopoverTheme?.diagnostics()" in controller
    assert "changed::color-scheme" in integration
    assert "this._layout !== 'Minimal'" in integration
    assert "statusArea?.quickSettings?.menu?.actor" in integration
    assert "statusArea?.dateMenu" in integration
    assert "Main.messageTray?._bannerBin" in integration
    assert "'child-added', 'child-removed'" in integration
    assert "actor.connect('destroy'" in integration
    assert "this._records.delete(actor)" in integration
    assert "implementation: 'layout-switcher-runtime'" in integration
    assert "layout-switcher-light-quick-settings" in stylesheet
    assert "layout-switcher-light-date-menu" in stylesheet
    assert "layout-switcher-light-notification-banner" in stylesheet
    assert ".layout-switcher-light-quick-settings .message" in stylesheet
    assert "layout-switcher-g-unity-notifications .message-list-placeholder" in stylesheet
    assert "color: rgba(34, 34, 38, 0.5) !important" in stylesheet
    assert ".layout-switcher-light-date-menu .calendar-day" in stylesheet
    assert ".layout-switcher-light-date-menu .message" in stylesheet
    assert ".popup-menu-content.frosted-glass-shell-surface.quick-settings" in stylesheet


def test_runtime_applies_owned_dock_settings_without_rebuilding_active_surface():
    controller = (RUNTIME / "runtimeController.js").read_text()
    dock = (RUNTIME / "dockRuntime.js").read_text()

    assert "_dockOpacityForProfile(profile)" in controller
    assert "_dockSizeForProfile(profile)" in controller
    assert "this._applyOpacity(opacity)" in dock
    assert "this._applyIconSize(iconSize)" in dock
    assert "set_double('background-opacity', opacity / 100)" in dock
    assert "set_int('dash-max-icon-size', iconSize)" in dock
    assert "managerGeneration: this._managerGeneration" in dock
    assert "this._managerGeneration++" in dock
    active_branch = dock[dock.index("if (this._active) {"):]
    for application in (
        "this._applyIndicator(indicator)",
        "this._applyHover(hover, magnificationIntensity)",
        "this._applyOpacity(opacity)",
        "this._applyIconSize(iconSize)",
        "this._host.visibilityModes.apply(visibility)",
    ):
        assert active_branch.index(application) < active_branch.index("return;")


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


def test_runtime_owns_taskbar_visibility_modes_and_strut_telemetry():
    controller = (RUNTIME / "runtimeController.js").read_text()
    runtime = (RUNTIME / "taskbarRuntime.js").read_text()
    visibility = (RUNTIME / "taskbarVisibilityModes.js").read_text()

    assert "panel-visibility-overrides" in controller
    assert "'panel-visibility-overrides'," in controller
    assert "`changed::${key}`" in controller
    assert "this._settingsChangedIds" in controller
    assert "new TaskbarVisibilityModes(" in runtime
    assert "this._visibilityModes.apply(visibility)" in runtime
    assert "intellihide-only-secondary" in visibility
    assert "set_int('intellihide-enable-start-delay', 0)" in visibility
    assert "intellihide-hide-from-windows" in visibility
    assert "FOCUSED_WINDOWS" in visibility
    assert "affectsStruts" in visibility
    delay = visibility.index("set_int('intellihide-enable-start-delay', 0)")
    enable = visibility.index("set_boolean('intellihide', selected !== 'always-visible')")
    assert delay < enable
    assert "window: this._windowDiagnostics()" in runtime
    assert "get_work_area_for_monitor" in runtime
    for mode in ("always-visible", "always-hidden", "intelligent"):
        assert mode in visibility


def test_runtime_telemetry_accounts_for_panel_height_overrides():
    controller = (RUNTIME / "runtimeController.js").read_text()
    runtime = (RUNTIME / "taskbarRuntime.js").read_text()
    surface = (RUNTIME / "taskbarSurface.js").read_text()

    assert "'panel-height-overrides'," in controller
    assert "_panelHeightForProfile(profile)" in controller
    assert "_panelActorHeightForProfile(profile)" in controller
    assert "get_value('panel-height-overrides')" in controller
    assert "panelHeight + profile.actorHeight - profile.panelHeight" in controller
    assert "actorHeight: this._panelActorHeightForProfile(profile)" in controller
    assert "this._surface.setPanelHeight(panelHeight)" in runtime
    assert "await this._surface.enable(panelHeight)" in runtime
    assert "PanelSettings.setPanelSize(Context.SETTINGS, index, panelHeight)" in surface


def test_runtime_owns_taskbar_opacity_and_reports_effective_alpha():
    controller = (RUNTIME / "runtimeController.js").read_text()
    runtime = (RUNTIME / "taskbarRuntime.js").read_text()

    assert "'panel-opacity-overrides'," in controller
    assert "_panelOpacityForProfile(profile)" in controller
    assert "get_value('panel-opacity-overrides')" in controller
    assert "? this._dockOpacityForProfile(profile)" in controller
    assert ": this._panelOpacityForProfile(profile)" in controller
    assert "this._applyOpacity(opacity)" in runtime
    assert "set_boolean('trans-use-custom-opacity', true)" in runtime
    assert "set_boolean('trans-use-dynamic-opacity', false)" in runtime
    assert "set_double('trans-panel-opacity', opacity / 100)" in runtime
    assert "Math.round(panel.dynamicTransparency.alpha * 100)" in runtime


def test_runtime_owns_minimal_native_panel_opacity_and_visibility():
    controller = (RUNTIME / "runtimeController.js").read_text()
    profiles = (RUNTIME / "layoutProfiles.js").read_text()
    integration = (RUNTIME / "nativePanelOpacityIntegration.js").read_text()

    assert "new NativePanelOpacityIntegration()" in controller
    assert "this._nativePanelOpacity.activate(panelOpacity, panelVisibility)" in controller
    assert "this._nativePanelOpacity.deactivate()" in controller
    assert "nativePanelOpacity:" in controller
    assert "panelOpacity: 65" in profiles
    assert "panelVisibility: 'always-visible'" in profiles
    assert "Main.panel" in integration
    assert "get_background_color()" in integration
    assert "background-color: rgba(" in integration
    assert "'notify::style'" in integration
    assert "this._originalStyle = style" in integration
    assert "this._repairCount++" in integration
    assert "this._panel.set_style(this._originalStyle)" in integration
    assert "styleOwned:" in integration
    assert "styleSignalOwned:" in integration
    assert "visibilitySignalsOwned:" in integration
    assert "_focusWindowTouchesPanel()" in integration
    assert "Main.layoutManager.addTopChrome" in integration
    assert "'leave-event'" in integration
    assert "this._panelActorData.affectsStruts" in integration
    assert "restoreConflicts:" in integration


def test_runtime_leaves_surface_borders_to_frosted_glass():
    dock_theme = (RUNTIME / "dock/theming.js").read_text()
    taskbar_transparency = (RUNTIME / "taskbar/transparency.js").read_text()
    glass_surface = (
        ROOT
        / "usr/share/gnome-shell/extensions/"
        "frosted-glass@communitybig.org/shellBlurSurface.js"
    ).read_text()

    assert "const borderlessStyle = 'border: 0 solid transparent;'" in dock_theme
    assert dock_theme.count("'border: 0 solid transparent;'") >= 3
    assert "border-color:${this._customizedBorder}" not in dock_theme
    assert "this._borderStyle = 'border: 0 solid transparent;'" in taskbar_transparency
    glass_border = "borderless ? 'border: none; ' : `border: 1px solid ${borderColor}; `"
    assert glass_border in glass_surface
    for layout in ("hybrid.txt", "classic.txt"):
        assert "trans-use-border=false" in (LAYOUTS / layout).read_text()


def test_runtime_keeps_taskbar_surface_alive_between_taskbar_profiles():
    controller = (RUNTIME / "runtimeController.js").read_text()
    runtime = (RUNTIME / "taskbarRuntime.js").read_text()
    branch_start = controller.index("profile.surface === RuntimeSurface.TASKBAR")
    taskbar_branch = controller[branch_start:controller.index(
        "profile.surface === RuntimeSurface.NATIVE", branch_start
    )]

    assert taskbar_branch.count("this._taskbar.deactivate()") == 1
    assert "generation !== this._syncGeneration" in taskbar_branch
    assert "await this._taskbar.activate(" in taskbar_branch
    assert taskbar_branch.index("await this._taskbar.activate(") < taskbar_branch.index(
        "this._taskbar.deactivate()"
    )
    active_branch = runtime[runtime.index("if (this._active) {"):]
    assert active_branch.index("this._applyIndicator(indicator)") < active_branch.index("return;")
    assert active_branch.index("this._applyHover(hover)") < active_branch.index("return;")
    assert active_branch.index("this._applyOpacity(opacity)") < active_branch.index(
        "return;"
    )
    assert active_branch.index("this._visibilityModes.apply(visibility)") < active_branch.index("return;")


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
    assert "import {DockSurfaceManager, State}" in dock
    assert "CommunityPanelRuntime" not in taskbar
    assert "new TaskbarSurfaceManager(this._host)" in taskbar
    assert "ComponentHost" in dock
    assert "ComponentHost" in taskbar


def test_taskbar_renderer_modules_are_internalized_under_unified_runtime():
    renderer = RUNTIME / "taskbar"
    expected = {
        "appIcons.js",
        "i18n.js",
        "intellihide.js",
        "panel.js",
        "panelManager.js",
        "panelPositions.js",
        "panelSettings.js",
        "proximity.js",
        "runtimeContext.js",
        "taskbar.js",
        "transparency.js",
        "utils.js",
        "windowPreview.js",
    }

    assert {path.name for path in renderer.glob("*.js")} == expected
    for path in RUNTIME.glob("*.js"):
        assert "../community-panel@communitybig.org/" not in path.read_text()


def test_taskbar_lifecycle_is_owned_by_the_unified_runtime():
    taskbar = (RUNTIME / "taskbarRuntime.js").read_text()
    surface = (RUNTIME / "taskbarSurface.js").read_text()
    adapter = (
        ROOT
        / "usr/share/gnome-shell/extensions/community-panel@communitybig.org/extension.js"
    ).read_text()
    context = (RUNTIME / "taskbar/runtimeContext.js").read_text()

    assert "new TaskbarSurfaceManager(this._host)" in taskbar
    assert "await this._surface.enable(panelHeight)" in taskbar
    assert "this._surface.destroy()" in taskbar
    assert "new PanelManager.PanelManager(" in surface
    assert "this.panelHost, this.monitorHost" in surface
    assert "manager.enable();" in surface
    assert "manager?.disable();" in surface
    assert "Context.initializeRuntimeContext(this._host, this)" in surface
    assert "Context.clearRuntimeContext(this);" in surface
    assert "rendererImplementation" in surface
    assert "rendererModules: this._manager ? 13 : 0" in surface
    assert surface.index("manager?.disable();") < surface.index(
        "Context.clearRuntimeContext(this);"
    )
    assert "activationPending" in surface
    assert "appActionsOwned" in surface
    assert "interactionsOwned" in surface
    assert "indicatorRendererOwned" in surface
    assert "globalOwned" in surface
    assert "TaskbarSurfaceManager" in adapter
    assert "PanelManager" not in adapter
    assert "initializeRuntimeContext" in context
    assert "clearRuntimeContext" in context


def test_taskbar_app_actions_are_owned_with_a_rollback_fallback():
    actions = (RUNTIME / "taskbarAppActions.js").read_text()
    surface = (RUNTIME / "taskbarSurface.js").read_text()
    app_icons = (RUNTIME / "taskbar/appIcons.js").read_text()

    assert "new TaskbarAppActions(Context.SETTINGS)" in surface
    assert "this.appActions?.destroy()" in surface
    assert "appActions: this.appActions?.diagnostics()" in surface
    assert "DTP_EXTENSION?.appActions" in app_icons
    assert "DTP_EXTENSION.appActions.activate(" in app_icons
    for behavior in (
        "launchNewInstance",
        "minimizeWindow",
        "activateAllWindows",
        "activateFirstWindow",
        "cycleThroughWindows",
        "getInterestingWindows",
        "closeAllWindows",
    ):
        assert f"{behavior}(" in actions
    for action in (
        "'RAISE'",
        "'LAUNCH'",
        "'MINIMIZE'",
        "'CYCLE'",
        "'CYCLE-MIN'",
        "'TOGGLE-SHOWPREVIEW'",
        "'TOGGLE-CYCLE'",
        "'QUIT'",
        "'TOGGLE-SPREAD'",
    ):
        assert action in actions
    assert "actionCounts" in actions
    assert "lastAction" in actions
    assert "import GObject from 'gi://GObject';" in actions
    assert "GObject.signal_lookup(" in actions
    assert "GObject.signal_query(signalId)" in actions
    assert "signalQuery.param_types.map(() => null)" in actions
    assert "emit('grab-op-begin', null, null)" not in actions


def test_taskbar_previews_and_context_menus_are_runtime_owned_with_fallbacks():
    interactions = (RUNTIME / "taskbarInteractions.js").read_text()
    surface = (RUNTIME / "taskbarSurface.js").read_text()
    taskbar = (RUNTIME / "taskbar/taskbar.js").read_text()
    app_icons = (RUNTIME / "taskbar/appIcons.js").read_text()
    intellihide = (RUNTIME / "taskbar/intellihide.js").read_text()

    assert "new TaskbarInteractions()" in surface
    assert "this.interactions?.destroy()" in surface
    assert "new WindowPreview.PreviewMenu(panel)" in taskbar
    assert "adoptPreviewMenu(" in interactions
    assert "this.interactions.adoptPreviewMenu(" in surface
    assert "createContextMenu(" in app_icons
    assert "new TaskbarSecondaryMenu(" in app_icons
    assert "MENU: 8" in intellihide
    assert "revealAndHold(Hold.MENU)" in interactions
    assert "release(Hold.MENU)" in interactions


def test_taskbar_layout_indicators_are_runtime_rendered_with_fallbacks():
    renderer = (RUNTIME / "taskbarIndicatorRenderer.js").read_text()
    surface = (RUNTIME / "taskbarSurface.js").read_text()
    app_icons = (RUNTIME / "taskbar/appIcons.js").read_text()

    assert "new TaskbarIndicatorRenderer(Context.SETTINGS)" in surface
    assert "this.indicatorRenderer?.destroy()" in surface
    assert "DTP_EXTENSION?.indicatorRenderer?.style()" in app_icons
    assert "DTP_EXTENSION?.indicatorRenderer?.draw(" in app_icons
    assert "if (communityStyle)" in app_icons
    assert "style === 'hybrid' || isFocused ? 18 : 8" in renderer
    assert "drawCounts" in renderer


def test_taskbar_owns_native_panel_host_and_preserves_shell_status_actors():
    surface = (RUNTIME / "taskbarSurface.js").read_text()
    status = (RUNTIME / "taskbarStatusArea.js").read_text()
    status_fullscreen = (
        RUNTIME / "taskbarStatusFullscreenIntegration.js"
    ).read_text()
    host = (RUNTIME / "taskbarPanelHost.js").read_text()
    panel = (RUNTIME / "taskbar/panel.js").read_text()
    manager = (RUNTIME / "taskbar/panelManager.js").read_text()

    assert "new TaskbarStatusAreaHost()" in surface
    assert "new TaskbarStatusFullscreenIntegration(" in surface
    assert "new TaskbarPanelHost(" in surface
    assert "panelHost: this.panelHost?.diagnostics()" in surface
    assert "statusArea: this.statusAreaHost.diagnostics(" in surface
    assert "this.panelHost.create(this, monitor, isStandalone)" in manager
    assert "this.panelHost.release(p)" in manager
    assert "this._statusAreaHost.adopt(this)" in panel
    assert "this._statusAreaHost.restore(this)" in panel
    assert "_dtpOriginalParent" not in panel
    assert "panelBox.remove_child(Main.panel)" in host
    assert "panelBox.add_child(Main.panel)" in host
    assert "_rollbackCreate(" in host
    assert "this.panelHost?.releaseAll()" in surface
    assert "Object.entries(panel?.statusArea ?? {})" in status
    assert "panel?.statusArea?.dateMenu" in status
    assert "panel?.statusArea?.quickSettings" in status
    assert "quickSettings?.menu?._grid?.get_children?.()" in status
    assert "openMenus" in status
    assert "orphanRoles" in status
    assert "nativeMenuManagerPreserved" in status
    assert "get_transformed_position()" in status
    assert "addToStatusArea" not in status
    assert "destroy()" not in status
    assert "implementation: 'layout-switcher-runtime'" in status_fullscreen
    assert "in-fullscreen-changed" in status_fullscreen
    assert "MetaSurfaceContainerActor" in status_fullscreen
    assert "surface.set_position(0, 0)" in status_fullscreen
    assert "notify::allocation" in status_fullscreen
    assert "frame.width === monitor.width" in status_fullscreen
    assert "buffer.width === monitor.width" in status_fullscreen
    assert "trackFullscreen: !isOverview" in status_fullscreen
    assert "setIntellihideTracking(" in status_fullscreen
    assert "Object.assign(record.actorData, record.original)" in status_fullscreen
    assert "status/fullscreen state changed externally" in status_fullscreen
    assert "restorationPending" in status_fullscreen
    assert "orphanStyles" in status_fullscreen
    assert "this.statusFullscreen.style(this)" in panel
    assert "this.statusFullscreen.unstyle(this)" in panel
    assert "PanelStyle" not in panel
    assert "_adjustForOverview" not in panel
    intellihide = (RUNTIME / "taskbar/intellihide.js").read_text()
    assert "setIntellihideTracking(" in intellihide


def test_taskbar_monitor_topology_is_owned_outside_panel_manager():
    surface = (RUNTIME / "taskbarSurface.js").read_text()
    host = (RUNTIME / "taskbarMonitorHost.js").read_text()
    manager = (RUNTIME / "taskbar/panelManager.js").read_text()

    assert "new TaskbarMonitorHost()" in surface
    assert "this.monitorHost.bind(manager)" in surface
    assert "this.monitorHost.destroy(manager)" in surface
    assert "monitorHost: this.monitorHost.diagnostics()" in surface
    assert "this.monitorHost.createPanels(this)" in manager
    assert "changed::primary-monitor" in host
    assert "changed::multi-monitors" in host
    assert "monitors-changed" in host
    assert "PanelSettings.setMonitorsInfo(SETTINGS)" in host
    assert "manager.disable(true)" in host
    assert "manager.enable(true)" in host
    assert "changed::primary-monitor" not in manager
    assert "changed::multi-monitors" not in manager
    assert "monitors-changed" not in manager
    assert "  _reset()" not in manager
    assert "global.disconnect(this._shutdownId)" not in manager


def test_taskbar_global_shell_hooks_have_owned_transactional_lifecycle():
    surface = (RUNTIME / "taskbarSurface.js").read_text()
    hooks = (RUNTIME / "taskbarShellHooks.js").read_text()
    manager = (RUNTIME / "taskbar/panelManager.js").read_text()

    assert "new TaskbarShellHooks()" in surface
    assert "this.shellHooks.destroy(manager)" in surface
    assert "shellHooks: this.shellHooks.diagnostics()" in surface
    assert "this.shellHooks.prepare(this)" in manager
    assert "this.shellHooks.activate(this," in manager
    assert "this.shellHooks.finish(this)" in manager
    assert "this.shellHooks.destroy(this)" in manager
    assert "Object.getOwnPropertyDescriptor(object, key)" in hooks
    assert "_descriptorsMatch(current, record.installed)" in hooks
    assert "Shell hook changed externally" in hooks
    assert "restoreConflicts" in hooks
    assert "new InjectionManager()" in hooks
    assert "changed::stockgs-force-hotcorner" in hooks
    assert "message-banner-offset" in hooks
    assert "shutdown-cleanup" in hooks
    assert "AppDisplay.AppIcon.prototype" not in manager
    assert "LookingGlass.LookingGlass.prototype" not in manager
    assert "Main.messageTray._bannerBin.ease =" not in manager
    assert "delete Main.layoutManager.findIndexForActor" not in manager
    assert "Object.defineProperty(Main.panel, 'style'" not in manager


def test_taskbar_manager_services_have_owned_transactional_lifecycle():
    surface = (RUNTIME / "taskbarSurface.js").read_text()
    services = (RUNTIME / "taskbarServiceHost.js").read_text()
    overview = (RUNTIME / "taskbarOverviewIntegration.js").read_text()
    desktop_icons = (RUNTIME / "desktopIconsUsableArea.js").read_text()
    notifications = (RUNTIME / "taskbarNotificationMonitor.js").read_text()
    taskbar = (RUNTIME / "taskbarRuntime.js").read_text()
    dock_imports = (RUNTIME / "dock/imports.js").read_text()
    monitor = (RUNTIME / "taskbarMonitorHost.js").read_text()
    manager = (RUNTIME / "taskbar/panelManager.js").read_text()

    assert "new TaskbarServiceHost()" in surface
    assert "this.serviceHost.destroy(manager)" in surface
    assert surface.index("this.serviceHost.destroy(manager)") < surface.index(
        "this.shellHooks.destroy(manager)"
    )
    assert "serviceHost: this.serviceHost.diagnostics()" in surface
    assert "this.serviceHost" in surface
    assert "this.serviceHost.prepare(this)" in manager
    assert "this.serviceHost.activate(this)" in manager
    assert "this.serviceHost.bind(this)" in manager
    assert "this.serviceHost.releasePanels(this)" in manager
    assert "this.serviceHost.unbind(this)" in manager
    assert "this.serviceHost.destroy(this)" in manager
    assert "manager.serviceHost.activateOverview(" in monitor
    assert "new TaskbarOverviewIntegration(manager)" in services
    assert "./taskbarOverviewIntegration.js" in services
    assert "../community-panel@communitybig.org/overview.js" not in services
    assert not (
        ROOT
        / "usr/share/gnome-shell/extensions/community-panel@communitybig.org/overview.js"
    ).exists()
    assert "overviewIntegration" in services
    assert "implementation: 'layout-switcher-runtime'" in overview
    assert "Object.getOwnPropertyDescriptor(object, key)" in overview
    assert "_descriptorsMatch(current, record.installed)" in overview
    assert "Overview hook changed externally" in overview
    assert "overview-allocation" in overview
    assert "workspace-isolation" in overview
    assert "changed::stockgs-keep-dash" in overview
    assert "changed::overview-click-to-exit" in overview
    assert "changed::isolate-workspaces" in overview
    assert "changed::hot-keys" in overview
    assert "Main.overview.toggle()" in overview
    assert "Main.overview.show" not in overview
    assert "this._endHotkeyPreviewCycle()" in overview
    assert "this._clearTimeouts()" in overview
    assert "restoreConflicts" in overview
    assert "entryCount" in overview
    assert "exitCount" in overview
    assert "actorsCreated: 0" in overview
    assert "orphanActors: 0" in overview
    assert "Utils.GlobalSignalsHandler" not in overview
    assert "Utils.InjectionsHandler" not in overview
    assert "new InjectionManager()" not in overview
    assert "new TaskbarNotificationMonitor()" in services
    assert "./taskbarNotificationMonitor.js" in services
    assert "notificationMonitor" in services
    assert "Shell.WindowTracker.get_default()" in notifications
    assert "this._sourceRecords = new Map()" in notifications
    assert "this._sourceRecords.set(source" in notifications
    assert "this._recomputeTrayState(record.appId)" in notifications
    assert "state.unityUrgent" in notifications
    assert "totalNotifications" in notifications
    assert "urgentApps" in notifications
    assert "layout-switcher-runtime" in notifications
    assert "runtimeContext.js" not in notifications
    assert "Utils.GlobalSignalsHandler" not in notifications
    assert "new DesktopIconsUsableAreaClass(" in services
    assert "this._queueDesktopIconsMargins(manager);" in services
    assert "./desktopIconsUsableArea.js" in services
    assert "../desktopIconsUsableArea.js" in dock_imports
    assert "layout-switcher-runtime" in desktop_icons
    assert "setMarginsForExtension(this._ownerUuid, this._margins)" in desktop_icons
    assert "130cbc66-235c-4bd6-8571-98d2d8bba5e2" in desktop_icons
    assert "TASKBAR_MARGIN_OWNER = 'community-panel@communitybig.org'" in services
    assert "typeof owner === 'string'" in desktop_icons
    assert "recipientUuids" in desktop_icons
    assert "extension.uuid" in desktop_icons
    assert not (RUNTIME / "dock/desktopIconsIntegration.js").exists()
    assert not (
        ROOT
        / "usr/share/gnome-shell/extensions/community-panel@communitybig.org"
        / "desktopIconsIntegration.js"
    ).exists()
    assert "desktopIconsUsableArea?.diagnostics()" in (
        RUNTIME / "dockRuntime.js"
    ).read_text()
    assert "desktopBridge" in services
    assert "INTELLIHIDE_KEYBINDING" in services
    assert "GLib.Source.remove(this._desktopMarginsIdleId)" in services
    assert "changed::panel-sizes" in services
    assert "changed::panel-top-bottom-margins" in services
    assert "changed::panel-side-margins" in services
    assert "changed::panel-element-positions" in services
    assert "desktopMarginsPending" in services
    assert "outerSize: Math.round(panel?.geom?.outerSize ?? 0)" in taskbar
    assert "activationFailures" in services
    assert "new TaskbarOverviewIntegration" not in manager
    assert "new NotificationsMonitor" not in manager
    assert "DesktopIconsIntegration" not in manager
    assert "_setKeyBindings(" not in manager
    assert "GLib.idle_add" not in manager


def test_taskbar_window_telemetry_distinguishes_normal_and_desktop_windows():
    taskbar = (RUNTIME / "taskbarRuntime.js").read_text()

    assert "windowType = window.get_window_type()" in taskbar
    assert "normal: windowType === Meta.WindowType.NORMAL" in taskbar
    assert "wmClass: window.get_wm_class()" in taskbar


def test_internalized_taskbar_modules_use_the_separate_runtime_context():
    panel = RUNTIME / "taskbar"
    consumers = [
        "appIcons.js",
        "intellihide.js",
        "panel.js",
        "panelManager.js",
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
    app_icons = (
        ROOT
        / "usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/dock/appIcons.js"
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
    assert "setStyle(style)" in runtime
    assert "get_string('indicator-style')" not in runtime


def test_runtime_owns_dock_hover_effects():
    runtime = (RUNTIME / "dockHoverEffects.js").read_text()
    dock = (RUNTIME / "dockRuntime.js").read_text()
    dash = (
        ROOT
        / "usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/dock/dash.js"
    ).read_text()
    app_icons = (
        ROOT
        / "usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/dock/appIcons.js"
    ).read_text()
    stylesheet = (
        ROOT
        / "usr/share/gnome-shell/extensions/community-dock@communitybig.org/stylesheet.css"
    ).read_text()

    assert "new DockHoverEffects(" in dock
    assert "this._host.hoverEffects.setEffect(effect, magnificationIntensity)" in dock
    assert "applyStyle(dash)" in runtime
    assert "animate(actor, position, iconSize)" in runtime
    assert "get_string('dock-hover-effect')" not in runtime
    assert "return this._effect" in runtime
    assert "scale_x: lift ? 1.08 : 1" in runtime
    assert "FRAME_INTERVAL_MS = 16" in runtime
    assert "const smooth = proximity * proximity * (3 - 2 * proximity)" in runtime
    assert "maxScale: 1 + this._intensity / 100" in runtime
    assert "renderer: 'ui-group-clone'" in runtime
    assert "new Clutter.Clone({" in runtime
    assert "Main.uiGroup.add_child(clone)" in runtime
    assert "Math.ceil(size * maximum)" in runtime
    assert "highResolutionSources:" in runtime
    assert "actor.opacity = 0" in runtime
    assert "actor.opacity = state.sourceOpacity" in runtime
    assert "releaseAll()" in runtime
    assert "hoverEffects.animate(actor, this._position, this.iconSize)" in dash
    assert "hoverEffects.applyStyle(this)" in dash
    assert "hoverEffects?.labelClearance(" in app_icons
    assert "magnificationClearance" in app_icons
    assert stylesheet.count("#dash.community-dock-hover-magnify") >= 6


def test_magnification_waits_until_the_dock_is_fully_shown():
    runtime = (RUNTIME / "dockRuntime.js").read_text()
    hover = (RUNTIME / "dockHoverEffects.js").read_text()

    assert "import {DockSurfaceManager, State}" in runtime
    assert "dash => this._dockIsShown(dash)" in runtime
    assert "dock?.getDockState?.() === State.SHOWN" in runtime
    assert "if (!this._isDockShown(dash))" in hover
    assert "this._suspend(record)" in hover
    assert "state.clone?.hide()" in hover
    assert "this._restoreSource(actor, state)" in hover


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
