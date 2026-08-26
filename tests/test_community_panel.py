# SPDX-License-Identifier: MIT
"""Community Panel packaging and migration contracts."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "usr/share/gnome-shell/extensions/community-panel@communitybig.org"
LAYOUTS = ROOT / "usr/share/layout-switcher/layouts"


def _section(layout: str, name: str) -> str:
    source = (LAYOUTS / layout).read_text()
    return source.split(f"[{name}]", 1)[1].split("\n\n", 1)[0]


def test_community_panel_has_distinct_identity_and_shell_support():
    metadata = json.loads((PANEL / "metadata.json").read_text())

    assert metadata["uuid"] == "community-panel@communitybig.org"
    assert metadata["name"] == "Community Panel"
    assert {"50", "51"}.issubset(metadata["shell-version"])
    assert metadata["upstream-version"] == 73
    assert metadata["fork-version"] == 1


def test_community_panel_preserves_dash_to_panel_73_core_baseline():
    expected = {
        "panel.js": "8dd0d19610f82568a1d539dc36766d1c5f0109babd632f506409a23bb0cfc1c2",
        "panelManager.js": "0be559edf513ed68791ef0fb55d776f18f5a0de7a57959f90ab124e979db9d87",
        "taskbar.js": "3b70a094b701291c2b6360d0105e8801610fe841c2120076e94fd1d5091fe427",
        "windowPreview.js": "0b61a11adad74464800bc63cefd2846faddb4bb969096a6dd99f2df1f4f92fb7",
        "stylesheet.css": "be6dbf8d2d8247a29200a7c8279e647018dfe501b713ec3e3c32a8204d512165",
    }

    for name, digest in expected.items():
        payload = (PANEL / name).read_bytes().replace(
            b"./runtimeContext.js",
            b"./extension.js",
        )
        assert hashlib.sha256(payload).hexdigest() == digest


def test_community_panel_matches_desk_ux_indicator_geometry():
    source = (PANEL / "appIcons.js").read_text()

    assert "Keep custom indicator geometry aligned with Community Dock." in source
    assert "communityStyle == 'hybrid' ? 18 : isFocused ? 18 : 8" in source


def test_community_panel_keeps_hybrid_indicator_at_fixed_length():
    source = (PANEL / "appIcons.js").read_text()

    assert "DOT_STYLE.SEGMENTED" in source
    assert "_getCommunityIndicatorStyle()" in source
    assert "return 'hybrid'" in source
    assert "return 'desk-ux'" in source
    assert "this._communityIndicatorFocused = isFocused" in source
    assert "this._unfocusedDots.set_size(0, 0)" in source
    assert "this._focusedDots.x_expand = true" in source
    assert "this._focusedDots.y_expand = true" in source
    assert "let visualScale = length > 0 ? targetLength / length : 1" in source
    assert "isHorizontalDots ? [visualScale, 1] : [1, visualScale]" in source
    assert "area.set_pivot_point(0.5, 0.5)" in source


def test_community_panel_preserves_license_provenance_schema_and_translations():
    assert "GNU GENERAL PUBLIC LICENSE" in (PANEL / "COPYING").read_text()
    upstream = (PANEL / "UPSTREAM.md").read_text()
    schema = (PANEL / "schemas/org.gnome.shell.extensions.dash-to-panel.gschema.xml").read_text()

    assert "Dash to Panel 73" in upstream
    assert "GPL-2.0-or-later" in upstream
    assert 'id="org.gnome.shell.extensions.dash-to-panel"' in schema
    assert (PANEL / "locale/pt_BR/LC_MESSAGES/dash-to-panel.mo").is_file()


def test_community_panel_runtime_does_not_require_an_active_extension_record():
    i18n = (PANEL / "i18n.js").read_text()
    desktop_icons = (PANEL / "desktopIconsIntegration.js").read_text()

    assert "Gettext.domain('dash-to-panel')" in i18n
    for name in ("appIcons.js", "panel.js", "windowPreview.js"):
        source = (PANEL / name).read_text()
        assert "gettext as _ } from './i18n.js'" in source or (
            name == "appIcons.js" and "gettext as _, ngettext } from './i18n.js'" in source
        )
        assert "gettext as _" not in source.split("./i18n.js", 1)[-1]
    assert "Extension.lookupByURL" not in desktop_icons
    assert "const PANEL_UUID = 'community-panel@communitybig.org'" in desktop_icons


def test_taskbar_layouts_use_only_unified_runtime():
    for layout in ("classic.txt", "hybrid.txt", "desk-ux.txt"):
        shell = _section(layout, "org/gnome/shell")
        enabled = next(
            line for line in shell.splitlines() if line.startswith("enabled-extensions=")
        )
        disabled = next(
            line for line in shell.splitlines() if line.startswith("disabled-extensions=")
        )

        assert "layout-switcher-runtime@communitybig.org" in enabled
        assert "community-panel@communitybig.org" not in enabled
        assert "dash-to-panel@jderose9.github.com" not in enabled
        assert "dash-to-panel@jderose9.github.com" not in disabled


def test_classic_panel_baseline_is_preserved():
    panel = _section("classic.txt", "org/gnome/shell/extensions/dash-to-panel")

    for setting in (
        'panel-positions=\'{"0":"BOTTOM"}\'',
        "panel-sizes='{\"0\":38}'",
        "group-apps=false",
        "focus-highlight=true",
        "focus-highlight-opacity=100",
        "dot-style-focused='SEGMENTED'",
        "trans-panel-opacity=0.70000000000000007",
    ):
        assert setting in panel


def test_hybrid_panel_baseline_is_preserved():
    panel = _section("hybrid.txt", "org/gnome/shell/extensions/dash-to-panel")

    for setting in (
        "panel-sizes='{\"0\":38}'",
        "group-apps=true",
        "animate-appicon-hover=true",
        "focus-highlight-opacity=30",
        "dot-size=3",
        "trans-panel-opacity=0.70000000000000007",
    ):
        assert setting in panel


def test_desk_ux_panel_baseline_is_preserved():
    panel = _section("desk-ux.txt", "org/gnome/shell/extensions/dash-to-panel")

    for setting in (
        'panel-positions=\'{"0":"BOTTOM"}\'',
        "panel-sizes='{\"0\":40}'",
        "panel-side-margins=3",
        "panel-top-bottom-margins=3",
        "dot-style-focused='METRO'",
        "dot-style-unfocused='DASHES'",
        "trans-panel-opacity=0.65000000000000002",
    ):
        assert setting in panel


def test_desk_ux_offers_the_gentle_hover_lift_without_enabling_it_by_default():
    panel = _section("desk-ux.txt", "org/gnome/shell/extensions/dash-to-panel")

    for setting in (
        "animate-appicon-hover=false",
        "animate-appicon-hover-animation-type='SIMPLE'",
        "animate-appicon-hover-animation-duration={'SIMPLE': uint32 220,",
        "animate-appicon-hover-animation-travel={'SIMPLE': 0.080000000000000002,",
        "animate-appicon-hover-animation-zoom={'SIMPLE': 1.0800000000000001,",
    ):
        assert setting in panel


def test_desk_ux_unfocused_indicator_is_neutral_gray():
    app_icons = (PANEL / "appIcons.js").read_text()

    color_method = app_icons.split("    _getRunningIndicatorColor(isFocused) {", 1)[1]
    color_method = color_method.split("    _getFocusHighlightColor() {", 1)[0]
    assert "!isFocused && this._getCommunityIndicatorStyle()" in color_method
    assert "red: 160" in color_method
    assert "green: 160" in color_method
    assert "blue: 168" in color_method
    assert "alpha: 184" in color_method


def test_panel_style_does_not_reparent_status_buttons_during_teardown():
    panel_style = (PANEL / "panelStyle.js").read_text()

    assert "this._refreshPanelButtons = true" in panel_style
    assert "this._refreshPanelButtons = false" in panel_style
    assert "this._refreshPanelButtons &&" in panel_style
    assert "if (!parent) return" in panel_style


def test_community_panel_context_menu_has_no_runtime_configuration():
    app_icons = (PANEL / "appIcons.js").read_text()

    assert "Dash to Panel Settings" not in app_icons
    assert "DTP_EXTENSION.openPreferences()" not in app_icons
    assert "Unlock taskbar" not in app_icons
    assert "Lock taskbar" not in app_icons


def test_community_panel_has_no_independent_preferences_ui():
    extension = (PANEL / "extension.js").read_text()
    panel_settings = (PANEL / "panelSettings.js").read_text()

    assert not (PANEL / "prefs.js").exists()
    assert not any((PANEL / "ui").glob("*"))
    assert "openPreferences()" not in extension
    assert "prefs-opened" not in extension
    assert "prefs-opened" not in panel_settings


def test_helper_and_applier_own_only_community_panel():
    helper = (
        ROOT
        / "usr/share/gnome-shell/extensions/layout-switcher-helper@communitybig.org/extension.js"
    ).read_text()
    applier = (ROOT / "usr/share/layout-switcher/layout_applier.py").read_text()

    assert "const COMMUNITY_PANEL_UUID = 'community-panel@communitybig.org'" in helper
    assert "const PANEL_UUIDS = [COMMUNITY_PANEL_UUID]" in helper
    assert "dash-to-panel@jderose9.github.com" not in helper
    assert "_panelWillRun()" in helper
    assert '_COMMUNITY_PANEL_UUID = "community-panel@communitybig.org"' in applier
    assert "_PANEL_UUIDS = (_COMMUNITY_PANEL_UUID,)" in applier
    assert "dash-to-panel@jderose9.github.com" not in applier
    assert "_restart_dash_to_panel_after_load(restart_uuids)" in applier


def test_package_compiles_panel_schema_and_installs_its_license():
    pkgbuild = (ROOT / "pkgbuild/PKGBUILD").read_text()

    assert (
        '"${pkgdir}/usr/share/gnome-shell/extensions/community-panel@communitybig.org/schemas"'
        in pkgbuild
    )
    assert "community-panel-GPL-2.0.txt" in pkgbuild
    assert "'gnome-shell-extension-dash-to-panel'" not in pkgbuild
