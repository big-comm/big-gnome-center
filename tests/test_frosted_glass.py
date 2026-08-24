"""Static contract tests for the bundled Frosted Glass extension."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "usr/share/gnome-shell/extensions/frosted-glass@communitybig.org"
SCHEMA = EXTENSION / "schemas/org.communitybig.frosted-glass.gschema.xml"


def test_metadata_supports_overview_on_gnome_50_and_full_backend_on_51():
    metadata = json.loads((EXTENSION / "metadata.json").read_text())

    assert metadata["uuid"] == "frosted-glass@communitybig.org"
    assert metadata["settings-schema"] == "org.communitybig.frosted-glass"
    assert metadata["shell-version"] == ["50", "51"]

    extension = (EXTENSION / "extension.js").read_text()
    assert "FULL_BACKEND_MINIMUM_SHELL_MAJOR = 51" in extension
    assert "if (FULL_BACKEND_AVAILABLE)" in extension
    assert "import('./shellSurfaces.js')" in extension
    assert "import('./windowController.js')" in extension
    assert "import {ShellSurfaces}" not in extension
    assert "import {WindowController}" not in extension


def test_bundled_layout_extensions_accept_gnome_51():
    base = ROOT / "usr/share/gnome-shell/extensions"
    for uuid in [
        "layout-switcher-helper@communitybig.org",
        "community-menu@communitybig.org",
    ]:
        metadata = json.loads((base / uuid / "metadata.json").read_text())
        assert "51" in metadata["shell-version"]


def test_schema_uses_layout_independent_path():
    schema = ET.parse(SCHEMA).getroot().find("schema")

    assert schema is not None
    assert schema.attrib["id"] == "org.communitybig.frosted-glass"
    assert schema.attrib["path"] == "/org/communitybig/frosted-glass/"


def test_schema_covers_requested_surfaces_and_rules():
    schema = ET.parse(SCHEMA).getroot().find("schema")
    keys = {node.attrib["name"] for node in schema.findall("key")}

    assert {
        "enabled",
        "windows-enabled",
        "panel-enabled",
        "dock-enabled",
        "layout-menus-enabled",
        "quick-settings-enabled",
        "calendar-enabled",
        "system-dialogs-enabled",
        "overview-enabled",
        "blur-strength",
        "glass-opacity",
        "use-accent-color",
        "blur-mode",
        "application-exclusions",
        "maximized-behavior",
        "fullscreen-behavior",
        "power-save-behavior",
    } <= keys


def test_overview_material_defaults_and_range():
    schema = ET.parse(SCHEMA).getroot().find("schema")
    keys = {node.attrib["name"]: node for node in schema.findall("key")}

    assert keys["blur-strength"].findtext("default") == "23"
    assert keys["glass-opacity"].findtext("default") == "37"
    assert keys["glass-opacity"].find("range").attrib == {"min": "0", "max": "100"}
    assert keys["use-accent-color"].findtext("default") == "false"


def test_automatic_mode_uses_live_background_blur():
    extension = (EXTENSION / "extension.js").read_text()

    assert "requestedMode === 'automatic' ? 'dynamic'" in extension
    assert "savingPower && powerBehavior === 'static'" in extension
    assert "MATERIAL_OPACITY_EXPONENT = 1.8" in extension
    assert "Math.pow(opacityPercent / 100, MATERIAL_OPACITY_EXPONENT)" in extension


def test_extension_does_not_depend_on_blur_my_shell_runtime():
    javascript = "\n".join(path.read_text() for path in EXTENSION.glob("*.js"))

    assert "blur-my-shell@aunetx" not in javascript
    assert "global.blur_my_shell" not in javascript


def test_package_and_layouts_do_not_depend_on_blur_my_shell():
    assert "gnome-shell-extension-blur-my-shell" not in (ROOT / "pkgbuild/PKGBUILD").read_text()
    for layout in (ROOT / "usr/share/layout-switcher/layouts").glob("*.txt"):
        assert "blur-my-shell@aunetx" not in layout.read_text()


def test_corner_shader_and_overview_are_project_owned():
    assert (EXTENSION / "roundedCorners.js").is_file()
    assert (EXTENSION / "roundedCorners.glsl").is_file()
    assert (EXTENSION / "overviewController.js").is_file()
    assert (EXTENSION / "shellBlurSurface.js").is_file()
    assert (EXTENSION / "blurPaintSignal.js").is_file()


def test_unsafe_window_fallback_is_gated_in_shell_and_ui():
    extension = (EXTENSION / "extension.js").read_text()
    controls = (ROOT / "usr/share/layout-switcher/ui/frosted_glass.py").read_text()

    assert "const WINDOW_FALLBACK_AVAILABLE = false" in extension
    assert "WINDOW_BLUR_AVAILABLE = False" in controls
    assert 'self._settings.set_boolean("windows-enabled", False)' in controls


def test_layout_switcher_exposes_frosted_glass_controls():
    effects = (ROOT / "usr/share/layout-switcher/ui/page_effects.py").read_text()
    controls = (ROOT / "usr/share/layout-switcher/ui/frosted_glass.py").read_text()

    assert "FrostedGlassControls(self._pool, self._toast)" in effects
    assert "if is_frosted_glass_supported():" in effects
    assert "shell_version[0] >= MINIMUM_SHELL_MAJOR" in controls
    assert "FULL_BACKEND_MINIMUM_SHELL_MAJOR = 51" in controls
    assert "_build_overview_main_group" in controls
    assert 'self._settings.set_boolean("overview-enabled", True)' in controls
    assert 'if _schema_has_key("use-accent-color"):' in controls
    for setting in [
        "panel-enabled",
        "dock-enabled",
        "layout-menus-enabled",
        "quick-settings-enabled",
        "calendar-enabled",
        "system-dialogs-enabled",
        "overview-enabled",
        "blur-strength",
        "glass-opacity",
        "use-accent-color",
        "blur-mode",
        "power-save-behavior",
    ]:
        assert setting in controls


def test_dock_material_overrides_and_restores_inline_background():
    surface = (EXTENSION / "shellBlurSurface.js").read_text()

    assert "DOCK_TRANSPARENT_STYLE" in surface
    assert "this.actor.get_style?.()" in surface
    assert "this.actor?.set_style?.(this._targetStyle)" in surface
    assert "this._effect.brightness = config.brightness" in surface
    assert "232, 234, 240" not in surface


def test_dash_to_panel_material_overrides_and_restores_inline_background():
    surface = (EXTENSION / "shellBlurSurface.js").read_text()
    discovery = (EXTENSION / "shellSurfaces.js").read_text()

    assert "DASH_TO_PANEL_TRANSPARENT_STYLE" in surface
    assert "DASH_TO_PANEL_CONTENT_TRANSPARENT_STYLE" in surface
    assert "'background-gradient-start: transparent'" in surface
    assert "'background-gradient-end: transparent'" in surface
    assert "this._kind === 'dash-to-panel'" in surface
    assert "this.actor?.set_style?.(this._targetStyle)" in surface
    assert "this._panelContent.set_style?.(this._panelContentStyle)" in surface
    assert "this.actor?.panel ?? null" in surface
    assert "this._panelContent, 'style-changed'" in surface
    assert "targets.set(panelInfo, 'dash-to-panel')" in discovery
    assert "!managedPanels.has(Main.panel)" in discovery


def test_dock_blur_tracks_dash_to_dock_slide_clip():
    surface = (EXTENSION / "shellBlurSurface.js").read_text()

    assert "findDockSlider" in surface
    assert "typeof current.slideX === 'number'" in surface
    assert "'notify::slide-x'" in surface
    assert "_visibleDockClip" in surface
    assert "this._overlay.set_clip(" in surface
    assert "this.actor.get_paint_opacity?.()" in surface


def test_popup_masks_use_theme_corner_radius():
    discovery = (EXTENSION / "shellSurfaces.js").read_text()
    surface = (EXTENSION / "shellBlurSurface.js").read_text()

    assert "'quick-settings': 36" in discovery
    assert "'date-menu': 28" in discovery
    assert "'notification-banner': 16" in discovery
    assert "themeCornerRadius: THEME_RADIUS_KINDS.has(kind)" in discovery
    assert "get_border_radius(St.Corner.TOPLEFT)" in surface
    assert "Number.isFinite(radius)" in surface


def test_shell_surfaces_preserve_theme_corner_geometry():
    discovery = (EXTENSION / "shellSurfaces.js").read_text()
    surface = (EXTENSION / "shellBlurSurface.js").read_text()

    for kind in [
        "'panel'",
        "'dash-to-panel'",
        "'dash-to-dock'",
        "'quick-settings'",
        "'date-menu'",
        "'notification-banner'",
    ]:
        assert kind in discovery.split("THEME_RADIUS_KINDS", 1)[1].split("]);", 1)[0]
    assert "themeCornerRadius: THEME_RADIUS_KINDS.has(kind)" in discovery
    assert "radius / Math.max(1, scale)" in surface
    assert "Number.isFinite(radius)" in surface


def test_dock_material_discovers_the_runtime_dock_background():
    discovery = (EXTENSION / "shellSurfaces.js").read_text()

    assert "name === 'dashtodockContainer'" in discovery
    assert "styleClasses(child).has('dash-background')" in discovery
    assert "targets.set(background, 'dash-to-dock')" in discovery
    assert "global.layoutSwitcherRuntime?.dockActor" not in discovery


def test_minimal_panel_material_preserves_square_borderless_geometry():
    surface = (EXTENSION / "shellBlurSurface.js").read_text()

    assert "const MINIMAL_PANEL_CLASS = 'layout-switcher-minimal-panel'" in surface
    assert "this.actor?.has_style_class_name?.(MINIMAL_PANEL_CLASS)" in surface
    assert "if (this._isBorderlessSurface())" in surface
    assert "borderless ? 'border: none; '" in surface
    assert "const cornerMaskChanged" in surface


def test_g_unity_panel_and_dock_are_borderless_material_surfaces():
    surface = (EXTENSION / "shellBlurSurface.js").read_text()

    assert "const GUNITY_PANEL_CLASS = 'layout-switcher-g-unity-panel'" in surface
    assert "const GUNITY_DOCK_CLASS = 'layout-switcher-g-unity-dock'" in surface
    assert "this.actor?.has_style_class_name?.(GUNITY_PANEL_CLASS)" in surface
    assert "this.actor?.has_style_class_name?.(GUNITY_DOCK_CLASS)" in surface
    assert "findStyledAncestor(this.actor, GUNITY_DOCK_CLASS)" in surface
    assert "PANEL_TRANSPARENT_STYLE" in surface
    assert "'border-width: 0px'" in surface


def test_quick_settings_neutralizes_content_and_pointer_borders():
    surface = (EXTENSION / "shellBlurSurface.js").read_text()
    stylesheet = (EXTENSION / "stylesheet.css").read_text()

    assert "QUICK_SETTINGS_TRANSPARENT_STYLE" in surface
    assert "QUICK_SETTINGS_POINTER_STYLE" in surface
    assert "findStyledAncestor(this.actor, 'popup-menu-boxpointer')" in surface
    assert "-arrow-border-width: 0px" in surface
    assert "this._pointerBorder.hide()" in surface
    assert "this._pointerBorder.visible = this._pointerBorderVisible" in surface
    assert "this._boxPointer.set_style?.(this._pointerStyle)" in surface
    assert "box-shadow: 0 8px 24px" not in stylesheet


def test_quick_settings_submenus_share_the_parent_blur():
    discovery = (EXTENSION / "shellSurfaces.js").read_text()
    stylesheet = (EXTENSION / "stylesheet.css").read_text()

    assert "QUICK_SUBMENU_CLASS = 'frosted-glass-quick-submenu'" in discovery
    assert "styleClasses(candidate).has('quick-toggle-menu')" in discovery
    assert "this._syncQuickSubmenus(quickSubmenus, config.lightMode)" in discovery
    assert "this._syncQuickSubmenus(new Set(), false)" in discovery
    assert ".frosted-glass-quick-submenu" in stylesheet
    assert "background-color: rgba(30, 31, 38, 0.42) !important" in stylesheet
    assert "box-shadow: none !important" in stylesheet


def test_calendar_and_notifications_are_an_independent_surface():
    discovery = (EXTENSION / "shellSurfaces.js").read_text()
    extension = (EXTENSION / "extension.js").read_text()
    stylesheet = (EXTENSION / "stylesheet.css").read_text()

    assert "config.calendarEnabled" in discovery
    assert "panel?.statusArea?.dateMenu" in discovery
    assert "dateMenu.menu.box" in discovery
    assert "targets.set(content, 'date-menu')" in discovery
    assert "Main.messageTray?._bannerBin" in discovery
    assert "Main.messageTray?._banner" in discovery
    assert "targets.set(banner, 'notification-banner')" in discovery
    assert "bannerBin.connect(signal, () => this._queueRefresh())" in discovery
    assert ".frosted-glass-shell-surface.notification-banner" in stylesheet
    assert ".message:second-in-stack" in stylesheet
    assert ".message:lower-in-stack" in stylesheet
    assert "background-color: rgba(30, 31, 38, 0.26) !important" in stylesheet
    assert "get_boolean('calendar-enabled')" in extension
    assert "POINTER_KINDS.has(this._kind)" in (EXTENSION / "shellBlurSurface.js").read_text()


def test_system_dialogs_are_an_independent_surface():
    discovery = (EXTENSION / "shellSurfaces.js").read_text()
    extension = (EXTENSION / "extension.js").read_text()
    stylesheet = (EXTENSION / "stylesheet.css").read_text()

    assert "config.systemDialogsEnabled" in discovery
    assert "Main.layoutManager.modalDialogGroup" in discovery
    assert "styleClasses(candidate).has('modal-dialog')" in discovery
    assert "targets.set(dialog, 'system-dialog')" in discovery
    assert "modalGroup.connect('child-added'" in discovery
    assert "this._queueRefresh()" in discovery
    assert "get_boolean('system-dialogs-enabled')" in extension
    assert ".frosted-glass-shell-surface.modal-dialog .modal-dialog-button" in stylesheet
    assert "box-shadow: none !important" in stylesheet


def test_glass_controls_avoid_per_actor_shadow_effects():
    stylesheet = (EXTENSION / "stylesheet.css").read_text()

    assert ".frosted-glass-shell-surface.quick-settings .quick-toggle" in stylesheet
    assert ".frosted-glass-shell-surface.datemenu-popover .calendar-day" in stylesheet
    assert ".frosted-glass-shell-surface.datemenu-popover .events-button" in stylesheet
    assert "background-color: rgba(30, 31, 38, 0.42)" in stylesheet
    assert "border: 1px solid rgba(255, 255, 255, 0.05) !important" in stylesheet
    assert "box-shadow: 0 2px 6px" not in stylesheet
    assert "box-shadow: 0 1px 4px" not in stylesheet


def test_glass_controls_follow_shell_accent_color():
    stylesheet = (EXTENSION / "stylesheet.css").read_text()

    assert "rgba(53, 132, 228" not in stylesheet
    assert "st-transparentize(-st-accent-color, 0.30)" in stylesheet
    assert "st-transparentize(-st-accent-color, 0.28)" in stylesheet
    assert "st-transparentize(-st-accent-fg-color, 0.88)" in stylesheet


def test_glass_material_tracks_light_and_dark_color_scheme():
    extension = (EXTENSION / "extension.js").read_text()
    surface = (EXTENSION / "shellBlurSurface.js").read_text()
    discovery = (EXTENSION / "shellSurfaces.js").read_text()
    overview = (EXTENSION / "overviewController.js").read_text()
    stylesheet = (EXTENSION / "stylesheet.css").read_text()

    assert "schema_id: 'org.gnome.desktop.interface'" in extension
    assert "'changed::color-scheme'" in extension
    assert (
        "const appLightMode = this._interfaceSettings.get_string('color-scheme') !==" in extension
    )
    assert "LIGHT_SHELL_MENU_LAYOUTS = new Set([1, 4])" in extension
    assert "Main.extensionManager.lookup(COMMUNITY_MENU_UUID)?.state" in extension
    assert "lightMode = appLightMode && communityMenuActive" in extension
    assert "brightness: lightMode ? 1.0 : 0.9" in extension
    assert "tintOpacity: materialOpacity" in extension
    assert "this._settings.settings_schema.has_key('use-accent-color')" in extension
    assert "this._settings.get_boolean('use-accent-color')" in extension
    assert "const LIGHT_STYLE_CLASS = 'frosted-glass-light'" in surface
    assert "config.lightMode ? '247, 248, 252'" in surface
    assert "materialColor(config, config.tintOpacity)" not in overview
    assert "record.tint" not in overview
    assert "this._syncQuickSubmenus(quickSubmenus, config.lightMode)" in discovery
    assert "lightMode: config.appLightMode" in discovery
    assert "brightness: config.appLightMode ? 1.0 : 0.9" in discovery
    assert ".quick-settings.frosted-glass-light" in stylesheet
    assert ".datemenu-popover.frosted-glass-light" in stylesheet
    assert ".modal-dialog.frosted-glass-light" in stylesheet
    assert ".frosted-glass-quick-submenu.frosted-glass-light" in stylesheet
    assert ".frosted-glass-overview.frosted-glass-light" in stylesheet
    assert "background-color: rgba(255, 255, 255, 0.48)" in stylesheet
    assert "border-color: rgba(0, 0, 0, 0.18)" in stylesheet
    assert (
        stylesheet.count("background-color: st-transparentize(-st-accent-color, 0.30) !important")
        >= 2
    )


def test_rounded_mask_matches_mutter_pixel_coverage():
    shader = (EXTENSION / "roundedCorners.glsl").read_text()
    effect = (EXTENSION / "roundedCorners.js").read_text()

    assert "circle_bounds" in shader
    assert "clip_radius + 0.5" in shader
    assert "center_left + 2.0" in shader
    assert "center_right - 1.0" in shader
    assert "width + 3 - 1e-6" in effect
    assert "height + 3 - 1e-6" in effect
    assert "notify::scale-factor" in effect
    assert "uniform sampler2D tex" in shader
    assert "texture2D(tex, uv)" in shader
    assert "min(coverage, color.a)" in shader
    assert "snippet.set_replace(body)" in effect


def test_shell_material_uses_one_outer_corner_mask():
    surface = (EXTENSION / "shellBlurSurface.js").read_text()

    assert "config.lightMode ? '247, 248, 252' : '24, 25, 31'" in surface
    assert "'rgba(0, 0, 0, 0.18)'" in surface
    assert "'rgba(255, 255, 255, 0.07)'" in surface
    assert "border-radius: ${this._cornerRadius}px" in surface
    assert "this._overlay.add_effect_with_name(" in surface


def test_shell_material_waits_for_a_mapped_allocated_target():
    surface = (EXTENSION / "shellBlurSurface.js").read_text()

    assert "this._lastConfig = config" in surface
    assert "if (!this._isReady())" in surface
    assert "if (!this.actor?.mapped)" in surface
    assert ".every(Number.isFinite)" in surface
    constructor = surface.split("constructor(actor, options)", 1)[1].split("update(config)", 1)[0]
    assert "_applyTargetStyle()" not in constructor


def test_overview_folder_tiles_reuse_the_blurred_backdrop():
    stylesheet = (EXTENSION / "stylesheet.css").read_text()

    assert ".frosted-glass-overview .overview-tile.app-folder" in stylesheet
    assert "background-color: rgba(24, 25, 31, 0.28) !important" in stylesheet


def test_overview_controls_reuse_the_blurred_backdrop():
    controller = (EXTENSION / "overviewController.js").read_text()
    material = (EXTENSION / "overviewMaterial.js").read_text()
    stylesheet = (EXTENSION / "stylesheet.css").read_text()

    assert "new OverviewMaterialStylesheet()" in controller
    assert "record.tint" not in controller
    assert "materialColor(config, config.tintOpacity)" not in controller
    assert "config.materialOpacity" in material
    assert "config.useAccentColor" in material
    assert "st-transparentize(-st-accent-color" in material
    assert "rgba(${neutral.join(', ')}, ${alpha.toFixed(3)})" in material
    assert ".search-section-content" in material
    assert ".overview-tile.app-folder" in material
    assert ".app-folder-dialog" in material
    assert ".app-folder-dialog .folder-name-entry" in material
    assert "#dash .overview-tile" in material
    assert "#dash .show-apps" in material
    assert ".grid-search-result:focus" in material
    assert "load_stylesheet" in material
    assert "unload_stylesheet" in material
    assert "UPDATE_DELAY_MS = 120" in material
    assert "GLib.timeout_add" in material
    assert "GLib.source_remove(this._updateId)" in material
    assert ".frosted-glass-overview .search-entry" in stylesheet
    assert ".frosted-glass-overview .workspace-thumbnail" in stylesheet
    assert ".frosted-glass-overview .search-section-content" in stylesheet
    assert ".frosted-glass-overview .overview-tile:focus" in stylesheet
    assert ".frosted-glass-overview .overview-tile:checked" in stylesheet
    assert ".frosted-glass-overview .grid-search-result:focus" in stylesheet
    assert "background-color: rgba(24, 25, 31, 0.28) !important" in stylesheet
    assert "background-color: rgba(200, 200, 200, 0.20) !important" in stylesheet
    assert "border-color: transparent !important" in stylesheet
    assert "box-shadow: none !important" in stylesheet


def test_overview_does_not_call_private_app_grid_loading_methods():
    controller = (EXTENSION / "overviewController.js").read_text()

    assert "_scheduleAppGridWarmup" not in controller
    assert "_redisplay" not in controller


def test_dynamic_blur_texture_is_replaced_by_outer_corner_mask():
    surface = (EXTENSION / "shellBlurSurface.js").read_text()
    effect = (EXTENSION / "roundedCorners.js").read_text()

    assert "this._overlay.add_effect_with_name(EFFECT_NAME" in surface
    assert "this._overlay, () => this._effect" in surface
    assert "this._overlay.add_effect_with_name(\n                CORNER_EFFECT_NAME" in surface
    assert "snippet.set_replace(body)" in effect


def test_dynamic_blur_uses_integrated_native_corner_mask():
    surface = (EXTENSION / "shellBlurSurface.js").read_text()

    assert "import Blur from 'gi://Blur';" in surface
    assert "new Blur.BlurEffect({mode: Blur.BlurMode.BACKGROUND})" in surface
    assert "this._effect.corner_radius = this._cornerRadius * scale" in surface
    assert "mode === 'static' && this._cornerRadius > 0" in surface
