# SPDX-License-Identifier: MIT
"""Static integration checks for the bundled Community Menu."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSION_DIR = ROOT / "usr/share/gnome-shell/extensions/community-menu@communitybig.org"
SCHEMA_FILE = (
    ROOT / "usr/share/glib-2.0/schemas/org.gnome.shell.extensions.community-menu.gschema.xml"
)


def test_community_menu_metadata_is_independent():
    metadata = json.loads((EXTENSION_DIR / "metadata.json").read_text())

    assert metadata["uuid"] == "community-menu@communitybig.org"
    assert metadata["gettext-domain"] == "community-menu"
    assert metadata["settings-schema"] == "org.gnome.shell.extensions.community-menu"
    assert "50" in metadata["shell-version"]
    assert metadata["version"] == 21


def test_community_menu_schema_exposes_only_supported_layouts():
    root = ET.parse(SCHEMA_FILE).getroot()
    enum = root.find("enum")
    schema = root.find("schema")

    assert enum is not None
    assert schema is not None
    assert [value.attrib["nick"] for value in enum.findall("value")] == [
        "ALL",
        "APPS_ONLY",
        "SYSTEM_ONLY",
        "APP_GRID",
        "MINT",
    ]
    assert [key.attrib["name"] for key in schema.findall("key")] == [
        "layout",
        "desktop-layout",
        "super-key-opens-menu",
    ]


def test_community_menu_replaces_arcmenu_package_dependency():
    pkgbuild = (ROOT / "pkgbuild/PKGBUILD").read_text()

    assert "gnome-shell-extension-arc-menu" not in pkgbuild
    assert "GPL-2.0-or-later" in pkgbuild
    assert "community-menu.mo" in pkgbuild
    assert "msgfmt --check" in pkgbuild


def test_menu_button_uses_bundled_community_icon():
    source = (EXTENSION_DIR / "widgets/menuButton.js").read_text()
    constants = (EXTENSION_DIR / "constants.js").read_text()

    assert (EXTENSION_DIR / "community-menu.svg").is_file()
    assert "${EXTENSION_PATH}/community-menu.svg" in source
    assert "MENU_BUTTON_ICON_SIZE = 36" in constants
    assert "style_class: 'community-menu-button-icon'" in source
    assert "style_class: 'popup-menu-icon'" not in source


def test_captured_events_tolerate_gnome_51_keyboard_api():
    source = (EXTENSION_DIR / "menu.js").read_text()

    assert "Main.keyboard?.maybeHandleEvent" in source
    assert "typeof maybeHandleEvent === 'function'" in source
    assert "maybeHandleEvent.call(Main.keyboard, event)" in source


def test_search_keyboard_input_uses_gnome_51_text_api_with_gnome_50_fallback():
    entry = (EXTENSION_DIR / "widgets/searchEntry.js").read_text()
    layout = (EXTENSION_DIR / "layouts/baseLayout.js").read_text()

    assert "typeof this._text?.set_input_interceptor === 'function'" in entry
    assert "this._text.set_input_interceptor(this.mapped ? global.stage : null)" in entry
    assert "this._text.set_input_interceptor(null)" in entry
    assert "this._text.event(event, false)" in entry
    assert "this._text.insert_unichar(String.fromCodePoint(unicode))" in entry
    assert "connectObject('activate', this._onActivate.bind(this), this)" in entry
    assert "this._searchResults?.activateDefault()" in entry
    assert (
        "this._searchEntry.startSearch(event);\n                return Clutter.EVENT_STOP;"
        in layout
    )


def test_menu_button_active_highlight_is_not_stretched_by_shell_padding():
    extension_source = (EXTENSION_DIR / "extension.js").read_text()
    menu_source = (EXTENSION_DIR / "menu.js").read_text()
    stylesheet = (EXTENSION_DIR / "stylesheet.css").read_text()

    assert "add_style_class_name('community-menu-panel-button')" in menu_source
    assert "#panel .panel-button.community-menu-panel-button" in stylesheet
    assert "-natural-hpadding: 0px" in stylesheet
    assert "-minimum-hpadding: 0px" in stylesheet
    assert "border-width: 0px" in stylesheet
    assert ".community-menu-button-icon" in stylesheet
    assert "icon-size: 36px" in stylesheet
    assert "#panel.dashtopanelMainPanel:overview .panel-button" in stylesheet
    assert "color: inherit" in stylesheet
    assert "community-menu-light-panel" in extension_source
    assert "community-menu-dark-panel" in extension_source
    assert "changed::color-scheme" in extension_source
    assert "CLASSIC_DESKTOP_LAYOUT = 'Classic'" in extension_source
    assert "DESK_UX_DESKTOP_LAYOUT = 'Desk UX'" in extension_source
    assert "changed::desktop-layout" in extension_source
    assert "community-menu-grid-panel" in extension_source
    assert "community-menu-light-panel" in stylesheet
    assert "community-menu-dark-panel" in stylesheet
    assert "community-menu-grid-panel" in stylesheet
    assert "icon-size: 38px" in stylesheet
    assert "padding: 1px" in stylesheet
    assert "border-radius: 999px !important" in stylesheet
    assert ".panel-button.community-menu-panel-button:hover" in stylesheet
    assert "#dashtopanelTaskbar .overview-tile:hover .dtp-container" in stylesheet
    assert ".panel-button.community-menu-panel-button:hover .panel-status-menu-box" in stylesheet
    assert ".overview-tile:hover .overview-icon" in stylesheet
    assert "background-color: rgba(238, 238, 236, 0.12) !important" in stylesheet
    assert "box-shadow: 0 0 0 2px rgba(238, 238, 236, 0.12) !important" in stylesheet
    assert "overflow: visible !important" in stylesheet
    assert "_syncFocusedIndicators" not in extension_source
    assert "Math.round(fullWidth / 2)" not in extension_source
    assert "color: #fafafb" in stylesheet
    assert "background-color: #222226" in stylesheet


def test_classic_categories_are_compact_and_open_cascade_on_hover():
    layout = (EXTENSION_DIR / "layouts/appListLayout.js").read_text()
    menu = (EXTENSION_DIR / "menu.js").read_text()
    sections = (EXTENSION_DIR / "sections.js").read_text()
    app_items = (EXTENSION_DIR / "widgets/appMenuItem.js").read_text()
    items = (EXTENSION_DIR / "widgets/miscMenuItems.js").read_text()
    constants = (EXTENSION_DIR / "constants.js").read_text()
    stylesheet = (EXTENSION_DIR / "stylesheet.css").read_text()

    assert "cascadeMenus: true" in layout
    assert "iconSize: Constants.COMPACT_CATEGORY_ICON_SIZE" in layout
    assert "monitorIndex: this._monitorIndex" in layout
    assert "COMPACT_CATEGORY_ICON_SIZE = 24" in constants
    assert "COMPACT_SUBMENU_ICON_SIZE = 18" in constants
    assert "APPS_ONLY_MENU_HEIGHT = 502" in constants
    assert "button.connectObject('notify::hover'" in sections
    assert "if (button.hover)" in sections
    assert "this._ensureCategoryMenu(button, category.get_menu_id())" in sections
    assert "this._openCategoryMenu(button, category.get_menu_id())" in sections
    assert "const CategoryAppsMenu = class extends PopupMenu.PopupMenu" in sections
    assert "openCascadeOnRight: this._desktopLayout === 'desk-ux'" in layout
    assert "inheritLightStyle: this._desktopLayout === 'desk-ux'" in layout
    assert "const side = openOnRight" in sections
    assert "? St.Side.LEFT" in sections
    assert "this._syncLightStyle()" in sections
    assert "has_style_class_name?.('community-menu-light')" in sections
    assert "this.actor.add_style_class_name('community-menu-light')" in sections
    assert "class CascadePopupMenuManager extends PopupMenu.PopupMenuManager" in sections
    assert "new CascadePopupMenuManager(this, params.cascadeExitActor)" in sections
    assert "event.get_coords()" in sections
    assert "this.activeMenu?.close(PopupAnimation.NONE)" in sections
    assert "this._ensureContent()" in sections
    assert "this._layout?.closePopups?.()" in menu
    assert "_init(app, isGrid, iconSize = Constants.APP_LIST_ICON_SIZE)" in app_items
    assert "_init(category, iconSize = Constants.APP_LIST_ICON_SIZE, showArrow = true)" in items
    assert "icon_size: iconSize" in items
    assert ".apps-only-layout-box .categories-list .popup-menu-item" in stylesheet
    assert ".community-category-submenu .apps-list" in stylesheet
    assert "max-height: 24em" not in stylesheet
    assert "padding: 6px 10px" in stylesheet
    assert "spacing: 8px" in stylesheet


def test_classic_menu_omits_all_apps_entry():
    layout = (EXTENSION_DIR / "layouts/appListLayout.js").read_text()

    assert "new MiscMenuItems.AllAppsMenuItem()" not in layout
    assert "this._allAppsButton" not in layout
    assert "new MiscMenuItems.BackMenuItem()" in layout


def test_classic_sidebar_uses_native_apps_and_session_actions():
    layout = (EXTENSION_DIR / "layouts/appListLayout.js").read_text()
    sections = (EXTENSION_DIR / "sections.js").read_text()
    session_buttons = (EXTENSION_DIR / "widgets/sessionButtons.js").read_text()
    stylesheet = (EXTENSION_DIR / "stylesheet.css").read_text()

    assert "new Sections.ClassicSidebarSection()" in layout
    assert "cascadeExitActor: this._sidebar" in layout
    assert "'org.bigcommunity.CommRelease.desktop'" in sections
    assert "'org.communitybig.layout-switcher.desktop'" in sections
    assert "'br.com.biglinux-settings.desktop'" in sections
    assert "'org.gnome.Calculator.desktop'" in sections
    assert "'org.gnome.TextEditor.desktop'" in sections
    assert "new SessionButtons.LogoutButton" in sections
    assert "new SessionButtons.RestartButton" in sections
    assert "new SessionButtons.PowerButton" in sections
    assert "appSystem.lookup_app(desktopId)" in sections
    assert "export const ApplicationButton" in session_buttons
    assert "this._app.activate()" in session_buttons
    assert ".classic-sidebar" in stylesheet
    assert ".classic-sidebar-separator" in stylesheet
    assert "icon-size: 26px" in stylesheet
    assert "border-radius: 10px" in stylesheet
    assert "background-color: rgba(128, 128, 128, 0.14)" in stylesheet
    assert ".community-menu-light .classic-sidebar-button:hover" in stylesheet
    assert "background-color: rgba(46, 46, 51, 0.18)" in stylesheet


def test_search_entry_tracks_light_color_scheme():
    extension_source = (EXTENSION_DIR / "extension.js").read_text()
    menu_source = (EXTENSION_DIR / "menu.js").read_text()
    stylesheet = (EXTENSION_DIR / "stylesheet.css").read_text()

    assert "menuButton.setLightStyle(lightMode)" in extension_source
    assert "menuButton.setLightStyle(false)" in extension_source
    assert "setLightStyle(enabled)" in menu_source
    assert "community-menu-light" in menu_source
    assert ".community-menu.community-menu-light .search-entry" in stylesheet
    assert "background-color: rgba(128, 128, 128, 0.14)" in stylesheet
    assert "color: #2e2e33" in stylesheet


def test_light_menu_styles_the_complete_popup():
    stylesheet = (EXTENSION_DIR / "stylesheet.css").read_text()

    assert ".community-menu.community-menu-light .popup-menu-content" in stylesheet
    assert "background-color: #fafafb" in stylesheet
    assert "border-color: #e6e6eb" in stylesheet
    assert ".community-menu.community-menu-light .popup-menu-item" in stylesheet
    assert ".community-menu.community-menu-light .app-item:hover" in stylesheet
    assert ".community-menu.community-menu-light StButton:active" in stylesheet
    assert ".popup-separator-menu-item .popup-separator-menu-item-separator" in stylesheet
    assert ".community-menu.community-menu-light StScrollBar > .vhandle" in stylesheet


def test_classic_search_results_are_compact_without_description_tooltips():
    layout = (EXTENSION_DIR / "layouts/appListLayout.js").read_text()
    sections = (EXTENSION_DIR / "sections.js").read_text()
    search = (EXTENSION_DIR / "search.js").read_text()
    stylesheet = (EXTENSION_DIR / "stylesheet.css").read_text()

    assert "Constants.APP_LIST_ICON_SIZE,\n            true" in layout
    assert "compactSearch = false" in sections
    assert "isGrid, monitorIndex, compactSearch" in sections
    assert "this.useTooltip = !compact" in search
    assert "this.description = null" in search
    assert "ellipsize: Pango.EllipsizeMode.END" in search
    assert "community-list-search-result-labels" in search
    assert "style_class: 'list-search-result'" not in search
    assert "compact-search-results" in search
    assert ".compact-search-results .popup-menu-item" in stylesheet
    assert "min-height: 30px" in stylesheet


def test_app_grid_menu_uses_monitor_center_anchor():
    source = (EXTENSION_DIR / "menu.js").read_text()
    assert "SETTINGS.get_enum('layout') === Constants.LAYOUTS.APP_GRID" in source
    assert "SETTINGS.get_string('desktop-layout')" in source
    assert ".toLowerCase()" in source
    assert ".replaceAll(' ', '-')" in source
    assert "=== 'desk-ux'" in source
    assert "if (!centerDeskUxMenu)" in source
    assert "Main.layoutManager.getWorkAreaForMonitor(this._monitorIndex)" in source
    assert "workArea.x + workArea.width / 2" in source
    assert "this._boxPointer.setPosition(this._centerAnchor, 0.5)" in source


def test_app_grid_uses_compact_windows_style_header_and_session_footer():
    layout = (EXTENSION_DIR / "layouts/appGridLayout.js").read_text()
    stylesheet = (EXTENSION_DIR / "stylesheet.css").read_text()

    assert "style_class: 'grid-header-box'" in layout
    assert "this._searchEntry.x_align = Clutter.ActorAlign.CENTER" in layout
    assert "new SessionButtons.SuspendButton" in layout
    assert "new SessionButtons.LogoutButton" in layout
    assert "new SessionButtons.RestartButton" in layout
    assert "new SessionButtons.PowerButton" in layout
    assert "new SessionButtons.PowerMenuButton" not in layout
    assert "style_class: 'session-actions-box'" in layout
    assert ".community-menu .grid-layout-box .grid-header-box {" in stylesheet
    assert "border-bottom: 1px solid rgba(255, 255, 255, 0.08)" in stylesheet
    assert "background-color: rgba(255, 255, 255, 0.055)" in stylesheet
    assert "border-bottom-color: rgba(46, 46, 51, 0.12)" in stylesheet
    assert ".grid-header-box .search-entry" in stylesheet
    assert ".grid-header-box .search-entry:hover" in stylesheet
    assert ".grid-header-box .search-entry:focus" in stylesheet
    assert "width: 44em" in stylesheet
    assert "background-color: transparent !important" in stylesheet
    assert "background-image: none !important" in stylesheet
    assert "border-color: transparent !important" in stylesheet
    assert (
        ".community-menu-light .grid-layout-box .grid-header-box .search-entry:focus" in stylesheet
    )
    assert ".grid-header-box .search-entry:focus .search-entry-icon" in stylesheet
    assert "color: rgba(46, 46, 51, 0.78) !important" in stylesheet
    assert "caret-color: #2e2e33 !important" in stylesheet
    assert "border-width: 0" in stylesheet
    assert "box-shadow: none" in stylesheet
    assert ".apps-menu StScrollBar" in stylesheet
    assert "min-width: 6px" in stylesheet
    assert ".session-actions-box" in stylesheet


def test_hybrid_layout_matches_enterprise_menu_structure():
    layouts = (EXTENSION_DIR / "layouts/layouts.js").read_text()
    layout = (EXTENSION_DIR / "layouts/hybridLayout.js").read_text()
    backend = (EXTENSION_DIR / "appsbackend.js").read_text()
    sections = (EXTENSION_DIR / "sections.js").read_text()
    items = (EXTENSION_DIR / "widgets/miscMenuItems.js").read_text()
    constants = (EXTENSION_DIR / "constants.js").read_text()
    stylesheet = (EXTENSION_DIR / "stylesheet.css").read_text()

    assert "new HybridLayout.HybridLayout" in layouts
    assert "new UserWidgets.UserMenuItem" in layout
    assert "new SearchEntry.SearchEntry" in layout
    assert "new Sections.HybridCategoriesSection" in layout
    assert "Constants.HYBRID_COLUMN_COUNT" in layout
    assert "new SessionButtons.LogoutButton" in layout
    assert "new SessionButtons.LockButton" in layout
    assert "new SessionButtons.RestartButton" in layout
    assert "new SessionButtons.PowerButton" in layout
    assert "frequentAppsCategory" in backend
    assert "recentFilesCategory" in backend
    assert "Shell.AppUsage.get_default()" in backend
    assert "class HybridCategoriesSection" in sections
    assert "Constants.COMPACT_SUBMENU_ICON_SIZE" in sections
    assert "notify::hover" in sections
    assert "this._selected(button, category.get_menu_id())" in sections
    assert "iconSize = Constants.APP_LIST_ICON_SIZE, showArrow = true" in items
    assert "if (showArrow)" in items
    assert "gridColumns = Constants.COLUMN_COUNT" in sections
    assert "HYBRID_COLUMN_COUNT = 4" in constants
    assert "HYBRID_MENU_HEIGHT = 620" in constants
    assert ".hybrid-layout-box .hybrid-box" in stylesheet
    assert "width: 62em" in stylesheet
    assert "width: 12em" in stylesheet
    assert "padding: 6px 8px" in stylesheet
    assert ".hybrid-session-actions" in stylesheet


def test_layout_menus_use_super_key_and_restore_default_handler():
    source = (EXTENSION_DIR / "extension.js").read_text()
    sync_body = source.split("    _syncOverlayKeyBinding() {", 1)[1].split(
        "    _enableOverlayKeyBinding() {", 1
    )[0]

    assert "SETTINGS.get_boolean('super-key-opens-menu')" in source
    assert "changed::super-key-opens-menu" in source
    assert "this._enableOverlayKeyBinding();" in sync_body
    assert "this._disableOverlayKeyBinding();" not in sync_body
    assert "layoutUsesMenu" not in source
    assert "GObject.signal_handler_find(" in source
    assert "{signalId: 'overlay-key'}" in source
    assert "GObject.signal_handler_block" in source
    assert "global.display.connectObject('overlay-key'" in source
    assert "this._toggleMenu()" in source
    assert "Main.overview.toggle()" in source
    assert "GObject.signal_handler_unblock" in source
    assert "this._mutterSettings.set_value('overlay-key', this._savedOverlayKey)" in source
    assert "this._getActivePanelExtension();\n            this._enableButtons();" in source
    assert "existingButton?.get_parent()" in source


def test_search_entry_handles_temporarily_missing_stage_focus():
    source = (EXTENSION_DIR / "widgets/searchEntry.js").read_text()

    assert "const appearFocused = focus" in source
    assert "!this._searchResults || !this._text" in source
    assert "this.contains(focus) || this._searchResults.contains(focus)" in source


def test_search_results_own_provider_displays_without_shared_provider_state():
    source = (EXTENSION_DIR / "search.js").read_text()

    assert "this._providerDisplays = new Map()" in source
    assert "this._providerDisplays.set(provider, providerDisplay)" in source
    assert "this._providerDisplays.get(provider)" in source
    assert "provider[this._displayId]" not in source
