# SPDX-License-Identifier: MIT
"""Static checks for the in-shell layout switch helper."""

from pathlib import Path

HELPER = (
    Path(__file__).resolve().parents[1]
    / "usr/share/gnome-shell/extensions/layout-switcher-helper@communitybig.org/extension.js"
)
HELPER_STYLESHEET = HELPER.with_name("stylesheet.css")


def test_live_color_switch_empties_shell_rebase_slices():
    source = HELPER.read_text()

    assert source.index("_moveExtensionLast(mgr, uuid)") < source.index(
        "mgr.disableExtension(uuid)"
    )
    assert source.index("_moveExtensionLast(mgr, livePanelUuid)") < source.index(
        "mgr.disableExtension(livePanelUuid)"
    )
    assert "const CLASSIC_MENU_LAYOUT = 1" in source
    assert "const HYBRID_MENU_LAYOUT = 4" in source
    assert "const ARCMENU_UUID" not in source
    assert "ARCMENU_HYBRID_LAYOUT" not in source
    assert "COMMUNITY_LIGHT_ICON_LAYOUTS" not in source
    assert "? 'bigicons-papient-dark'" in source
    assert "? 'bigicons-papient-light'" in source
    assert "const DESK_UX_MENU_LAYOUT = 3" in source
    assert "const nativeShell = this._activeLayoutLabel === 'Classic'" in source
    assert "this._activeLayoutLabel === 'Hybrid';" in source
    assert "hybridArcMenu" not in source
    assert "!live.has(COMMUNITY_MENU_UUID)" in source
    assert "this._activeLayoutLabel === 'Desk UX'" in source
    assert "this._onColorSchemeChanged(false)" in source
    assert "const managedNativeState = nativeShell" in source
    assert "const manageShell = reconcileShell && managedNativeState" in source
    assert "manageShell ? 'managed' : 'preserved'" in source
    assert "? [LIGHT_STYLE_UUID, USER_THEME_UUID]" in source
    assert "if (!(nativeShell && dark) && !isLive(wantOn))" in source
    assert "Main.setThemeStylesheet(null)" in source


def test_menu_layouts_hide_only_the_desktop_power_fallback():
    source = HELPER.read_text()

    assert "const HELPER_BUILD = 72" in source
    assert "get_strv('enabled-extensions')" in source
    assert "_panelWillRun()" in source
    assert "_usesMenuSessionActions()" in source
    assert "layout === CLASSIC_MENU_LAYOUT" in source
    assert "layout === DESK_UX_MENU_LAYOUT" in source
    assert "layout === HYBRID_MENU_LAYOUT" in source
    assert "Main.panel.statusArea.quickSettings?._system" in source
    assert "indicator?._systemItem?.powerToggle" in source
    assert "!powerToggle.visible" in source
    assert "indicator.hide()" in source
    assert "indicator._syncIndicatorsVisible?.()" in source
    assert "'notify::visible', () => this._syncPanelSystemIndicator()" in source
    assert source.index("this._setupPanelSystemIndicator();") < source.index(
        "this._sleep(1000).then"
    )


def test_menu_layouts_hide_only_quick_settings_shutdown_action():
    source = HELPER.read_text()

    assert "_findQuickSettingsShutdownItem()" in source
    assert ".find(item => item?.menu === systemItem.menu)" in source
    assert "_setupQuickSettingsShutdownItem()" in source
    assert "_syncQuickSettingsShutdownItem()" in source
    assert "if (this._usesMenuSessionActions())" in source
    assert "item.hide()" in source
    assert "item._sync()" in source
    assert "_teardownQuickSettingsShutdownItem()" in source


def test_hybrid_light_panel_keeps_overview_icon_contrast():
    source = HELPER.read_text()
    stylesheet = HELPER_STYLESHEET.read_text()

    assert "LIGHT_OVERVIEW_PANEL_CLASS" in source
    assert "_syncLightOverviewPanelClass()" in source
    assert "_clearLightOverviewPanelClass()" in source
    assert "get_string('color-scheme') === 'prefer-dark'" in source
    assert "this._activeLayoutLabel !== 'Hybrid'" in source
    assert "global.dashToPanel?.panels" in source
    assert "layout-switcher-light-overview-panel:overview" in stylesheet
    assert "color: #222226" in stylesheet


def test_native_shell_running_indicators_follow_shell_accent():
    source = HELPER.read_text()
    stylesheet = HELPER_STYLESHEET.read_text()

    assert "const HELPER_BUILD = 72" in source
    assert "NATIVE_ACCENT_PANEL_CLASS" in source
    assert "_syncNativeAccentPanelClass()" in source
    assert "_clearNativeAccentPanelClass()" in source
    assert "const classicLayout = this._activeLayoutLabel === 'Classic'" in source
    assert "const deskUxLayout = this._activeLayoutLabel === 'Desk UX'" in source
    assert "const hybridLayout = this._activeLayoutLabel === 'Hybrid'" in source
    assert "const nativeAccentLayout = classicLayout || deskUxLayout || hybridLayout" in source
    assert "const accentIndicatorLayout = deskUxLayout || hybridLayout" in source
    assert "'changed::accent-color'" in source
    assert "_syncClassicFocusHighlight()" in source
    assert "Gio.SettingsSchemaSource.new_from_directory(" in source
    assert "this._panelSettings = new Gio.Settings" in source
    assert "get_string('focus-highlight-color')" in source
    assert "set_string('focus-highlight-color', accent)" in source
    assert "layout-switcher-accent-probe" in stylesheet
    assert "layout-switcher-native-accent-panel" in stylesheet
    assert "background-color: -st-accent-color" in stylesheet


def test_incremental_migration_detaches_menu_before_replacing_panel():
    source = HELPER.read_text()

    migration = source.index("async _applyLayout")
    hoist = source.index("steps.push('hoist self')", migration)
    reload_off = source.index("steps.push(`reload-off ${uuid}`)", migration)
    leaving = source.index("const leaving =", source.index("async _applyLayout"))
    assert hoist < reload_off < leaving


def test_dbus_export_retries_after_legacy_helper_releases_path():
    source = HELPER.read_text()

    assert "const DBUS_EXPORT_RETRY_MS = 250" in source
    assert "if (this._dbus || this._dbusRetry)" in source
    assert "retrying after legacy helper exits" in source
    assert "this._dbusRetry = GLib.timeout_add(" in source
    assert "if (!this._cancelled)\n                            this._export();" in source
    assert "GLib.Source.remove(this._dbusRetry)" in source


def test_icon_theme_change_refreshes_appindicator_cache():
    source = HELPER.read_text()

    assert "const APPINDICATOR_UUID = 'appindicatorsupport@rgcjonas.gmail.com'" in source
    assert "iconThemeChanged = true" in source
    assert "await this._refreshIconThemeConsumers()" in source
    assert "rescan_icon_theme?.()" in source
    assert "Gio.File.new_for_path(utilPath).get_uri()" in source
    assert "await import(utilUri)" in source
    assert "destroyDefaultTheme?.()" in source
    assert "Gio.File.new_for_path(actorPath).get_uri()" in source
    assert "appIndicatorModule = await import(actorUri)" in source
    assert "new appIndicatorModule.IconActor" in source
    assert "statusIcon._setIconActor(newIcon)" in source
    assert "Object.entries(Main.panel.statusArea)" in source
    assert "id.startsWith('appindicator-')" in source
    assert "refreshAllProperties?.()" in source
    assert "_invalidateIcon?.()" in source
    assert source.count("steps.push(`status icons refreshed ${refreshed}`)") == 2
    complete = source.index("async _completeSwitch")
    legacy = source.index("async _applyLayout")
    first_refresh = source.index("steps.push(`status icons refreshed ${refreshed}`)")
    second_refresh = source.index(
        "steps.push(`status icons refreshed ${refreshed}`)", first_refresh + 1
    )
    assert complete < first_refresh < legacy < second_refresh
    private_reset = source.index("destroyDefaultTheme?.()")
    actor_reset = source.index("_invalidateIcon?.()", private_reset)
    assert private_reset < actor_reset


def test_live_color_switch_supports_runtime_hosted_panel():
    source = HELPER.read_text()
    follower = source[source.index("async _followColorScheme"):source.index(
        "async _refreshIconThemeConsumers"
    )]

    assert "const panelWillRun = this._panelWillRun();" in follower
    assert "live.has(KIWI_UUID) || !panelWillRun" in follower
    assert "live.has(KIWI_UUID) || !livePanelUuid" not in follower
    assert "mgr.lookup(livePanelUuid ?? COMMUNITY_PANEL_UUID)" in follower


def test_live_color_switch_refreshes_tray_icons_after_shell_theme():
    source = HELPER.read_text()
    follower = source[source.index("async _followColorScheme"):source.index(
        "async _refreshIconThemeConsumers"
    )]

    assert follower.index("Main.loadTheme()") < follower.index(
        "await this._refreshIconThemeConsumers()"
    )
    assert "deferred icon-theme refresh failed" in follower


def test_biggnome_uses_helper_owned_floating_panel():
    source = HELPER.read_text()
    stylesheet = HELPER_STYLESHEET.read_text()

    assert "COMMUNITY_DOCK_UUID" in source
    assert "dash-to-dock@micxgx.gmail.com" not in source
    assert "BIGGNOME_PANEL_CLASS" in source
    assert "_syncBigGnomePanelClass()" in source
    assert "_clearBigGnomePanelClass()" in source
    assert "this._extensionWillRun(KIWI_UUID)" in source
    assert "#panel.layout-switcher-biggnome-panel" in stylesheet
    assert "background-color: rgba(0, 0, 0, 0.65)" in stylesheet
    assert "border-radius: 9999px" in stylesheet


def test_minimal_uses_helper_owned_rectangular_panel():
    source = HELPER.read_text()
    stylesheet = HELPER_STYLESHEET.read_text()

    assert "MINIMAL_PANEL_CLASS" in source
    assert "_syncMinimalPanelClass()" in source
    assert "_clearMinimalPanelClass()" in source
    assert "#panel.layout-switcher-minimal-panel" in stylesheet
    assert "background-color: rgba(0, 0, 0, 0.65)" in stylesheet
    assert "border-radius: 0" in stylesheet


def test_g_unity_uses_helper_owned_borderless_panel_and_dock():
    source = HELPER.read_text()
    stylesheet = HELPER_STYLESHEET.read_text()

    assert "GUNITY_PANEL_CLASS" in source
    assert "GUNITY_DOCK_CLASS" in source
    assert "_syncGUnitySurfaceClasses()" in source
    assert "_setupGUnityShell()" in source
    assert "active_layout" in source
    assert "#panel.layout-switcher-g-unity-panel" in stylesheet
    assert "#dashtodockContainer.layout-switcher-g-unity-dock" in stylesheet
    assert "border: none" in stylesheet
    assert "width: 340px" in stylesheet
    assert "max-width: 340px" in stylesheet
    assert "messageList.x_align = Clutter.ActorAlign.FILL" in source
    assert "messageList.x_expand = true" in source
    assert "layout-switcher-g-unity-quick-settings" in stylesheet
    assert "min-height: 3em" in stylesheet
    assert ".message-list.layout-switcher-g-unity-notifications" in stylesheet
    assert ".message-view:ltr" in stylesheet
    assert "margin-right: 0" in stylesheet
    assert "_syncGUnityNotificationIndicator" in source
    assert "notification-added" in source
    assert "notification-removed" in source
    assert "background-color: #ff3b30" in stylesheet
    assert "width: 8" in source
    assert "height: 8" in source
    assert "y_align: Clutter.ActorAlign.CENTER" in source
    assert ".dash-background" in stylesheet
    assert "background-color: transparent" in stylesheet
    assert "#panel.layout-switcher-g-unity-panel .panel-button" in stylesheet
    g_unity_buttons = stylesheet.split(
        "#panel.layout-switcher-g-unity-panel .panel-button {", 1
    )[1].split("}", 1)[0]
    assert "color: #fafafb;" in g_unity_buttons
    assert "-natural-hpadding: 8px" in stylesheet
    assert "Gjs_ui_dateMenu_DateMenuButton.panel-button" in stylesheet
    assert "_setupGUnityDndAction" in source
    assert "notifications-disabled-symbolic" in source
    assert "dndToggle.hide()" in source


def test_fixed_dark_layouts_resolve_the_shell_stylesheet_before_enable():
    source = HELPER.read_text()

    assert "const FIXED_DARK_LAYOUTS = new Set([" in source
    for layout in ("BigGnome", "Desk UX", "G-Unity", "Minimal"):
        assert f"'{layout}'" in source.split("const FIXED_DARK_LAYOUTS", 1)[1].split(
            "]);", 1
        )[0]
    assert "Main.sessionMode.colorScheme = 'force-dark'" in source
    assert "ensureValidColorScheme(FIXED_DARK_LAYOUTS.has(targetLayout))" in source
    color_sync = source.index(
        "ensureValidColorScheme(FIXED_DARK_LAYOUTS.has(targetLayout))"
    )
    theme_load = source.index("Main.loadTheme();", color_sync)
    first_enable = source.index("mgr.enableExtension(uuid)", theme_load)
    assert color_sync < theme_load < first_enable


def test_g_unity_shell_is_restored_before_extensions_are_disabled():
    source = HELPER.read_text()
    begin_switch = source.split("async _beginSwitch(payload) {", 1)[1]
    begin_switch = begin_switch.split("CompleteSwitchAsync", 1)[0]

    assert "this._isGUnityActive() && req.label !== 'G-Unity'" in begin_switch
    assert begin_switch.index("this._teardownGUnityShell();") < begin_switch.index(
        "for (const uuid of teardown)"
    )
    assert begin_switch.index("this._clearGUnitySurfaceClasses();") < begin_switch.index(
        "for (const uuid of teardown)"
    )


def test_biggnome_uses_compact_accent_aware_dock():
    source = HELPER.read_text()
    stylesheet = HELPER_STYLESHEET.read_text()

    assert "BIGGNOME_DOCK_CLASS" in source
    assert "_findActorsByName(" in source
    assert "'dashtodockContainer'" in source
    assert "_clearBigGnomeDockClass()" in source
    assert "layout-switcher-biggnome-dock.bottom.shrink" in stylesheet
    assert "margin-left: 0 !important" in stylesheet
    assert "padding: 4px !important" in stylesheet
    assert "margin-left: 2px" in stylesheet
    assert ".app-well-app.focused .app-grid-running-dot" in stylesheet
    assert "background-color: rgba(255, 255, 255, 0.35)" in stylesheet
    assert "background-color: -st-accent-color" in stylesheet


def test_biggnome_dock_style_is_released_before_runtime_teardown():
    source = HELPER.read_text()
    begin_switch = source.split("async _beginSwitch(payload) {", 1)[1]
    begin_switch = begin_switch.split("CompleteSwitchAsync", 1)[0]

    assert begin_switch.index("this._clearBigGnomeDockClass();") < begin_switch.index(
        "for (const uuid of teardown)"
    )


def test_clean_room_switch_yields_frames_between_shell_components():
    source = HELPER.read_text()
    begin_switch = source.split("async _beginSwitch(payload) {", 1)[1]
    begin_switch = begin_switch.split("CompleteSwitchAsync", 1)[0]
    complete_switch = source.split("async _completeSwitch(payload) {", 1)[1]
    complete_switch = complete_switch.split("AbortSwitchAsync", 1)[0]

    assert "const TRANSITION_FRAME_MS = 16" in source
    assert "_yieldTransitionFrame()" in source
    assert "return this._sleep(TRANSITION_FRAME_MS);" in source
    assert "await this._yieldTransitionFrame();" in begin_switch
    assert complete_switch.count("await this._yieldTransitionFrame();") == 2


def test_accent_indicators_preserve_layout_specific_sizes():
    source = HELPER.read_text()

    assert "const HYBRID_INDICATOR_SCALE = 0.8" in source
    assert "_waitDashToPanelReady" in source
    assert "panel?.taskbar?._box" in source
    assert "const targetPanelUuid = PANEL_UUIDS.find(uuid => target.has(uuid))" in source
    assert "await this._waitDashToPanelReady()" in source
    assert "_syncHybridFocusedIndicators()" in source
    assert "_teardownHybridFocusedIndicators()" in source
    assert "actor.has_style_class_name?.('dtp-dots-container')" in source
    assert "indicator.set_pivot_point(0.5, 0.5)" in source
    assert "for (const [index, indicator] of indicators.entries())" in source
    assert "const scale = this._activeLayoutLabel === 'Hybrid'" in source
    assert "? HYBRID_INDICATOR_SCALE" in source
    assert "indicator.set_scale(scale, 1)" in source
    assert "new Clutter.DesaturateEffect({factor: 1})" in source
    assert "_watchHybridTaskbarTree(taskbarBox)" in source
    assert "'child-added', (_parent, child)" in source
    assert "this._watchHybridTaskbarTree(child)" in source
    assert "_watchHybridIndicatorContainer(actor)" in source
    assert "'child-removed', (_container, indicator)" in source
    assert "for (const container of this._hybridIndicatorContainers" in source
    assert "for (const actor of this._hybridTaskbarActors" in source


def test_notification_positions_are_owned_by_the_shell_helper():
    source = HELPER.read_text()

    for layout, position in (
        ("Classic", "bottom-right"),
        ("Hybrid", "bottom-right"),
        ("Desk UX", "bottom-right"),
        ("Minimal", "top-center"),
        ("BigGnome", "top-center"),
        ("G-Unity", "top-right"),
    ):
        assert f"['{layout}', '{position}']" in source

    for position in (
        "top-left",
        "top-center",
        "top-right",
        "bottom-left",
        "bottom-center",
        "bottom-right",
    ):
        assert f"['{position}'," in source

    assert '<method name="SetNotificationPosition">' in source
    assert "Main.messageTray?._bannerBin" in source
    assert "bannerBin.set_x_align(xAlign)" in source
    assert "bannerBin.set_y_align(yAlign)" in source
    assert "this._syncNotificationPosition();" in source
    assert "this._restoreNotificationPosition();" in source
    assert "notification_positions" in source
