# SPDX-License-Identifier: MIT
"""Tests for shipped layout dump portability."""

import ast
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LAYOUT_DIR = REPO_ROOT / "usr/share/layout-switcher/layouts"
MONITOR_KEYED_DTP_KEYS = {
    "panel-anchors",
    "panel-element-positions",
    "panel-lengths",
    "panel-positions",
    "panel-sizes",
}
MACHINE_MONITOR_IDS = {
    "Virtual-1",
    "eDP-1",
    "HDMI-1",
    "unknown-unknown",
}
COMMUNITY_MENU_UUID = "community-menu@communitybig.org"
ARCMENU_UUID = "arcmenu@arcmenu.com"
COMMUNITY_PANEL_UUID = "community-panel@communitybig.org"
COMMUNITY_DOCK_UUID = "community-dock@communitybig.org"
RUNTIME_UUID = "layout-switcher-runtime@communitybig.org"
USER_THEME_UUID = "user-theme@gnome-shell-extensions.gcampax.github.com"
LIGHT_STYLE_UUID = "light-style@gnome-shell-extensions.gcampax.github.com"
KIWI_UUID = "kiwi@kemma"
GTK4_DING_UUID = "gtk4-ding@smedius.gitlab.com"
LAYOUT_SWITCHER_HELPER_UUID = "layout-switcher-helper@communitybig.org"
LEGACY_LAYOUT_SWITCHER_HELPER_UUID = "layout-switcher-helper@bigcommunity.org"
BIG_SHOT_UUID = "big-shot@communitybig.org"
LEGACY_BIG_SHOT_UUID = "big-shot@bigcommunity.org"
PAMAC_UPDATES_UUID = "pamac-updates@manjaro.org"
GSCONNECT_UUID = "gsconnect@andyholmes.github.io"
REMOVABLE_DRIVE_MENU_UUID = "drive-menu@gnome-shell-extensions.gcampax.github.com"
COPYOUS_SECTION = "org/gnome/shell/extensions/copyous"
COMMUNITY_MENU_LAYOUTS = {
    "classic.txt": "APPS_ONLY",
    "desk-ux.txt": "APP_GRID",
    "hybrid.txt": "MINT",
}
COMMUNITY_MENU_DESKTOP_LAYOUTS = {
    "classic.txt": "Classic",
    "desk-ux.txt": "Desk UX",
    "hybrid.txt": "Hybrid",
}
NO_PANEL_MENU_LAYOUTS = {"biggnome.txt", "g-unity.txt", "minimal.txt"}


def _read_key_values(layout_text: str):
    for line in layout_text.splitlines():
        if "=" not in line or line.startswith("["):
            continue
        key, value = line.split("=", 1)
        yield key, value


def _section_key_values(layout_text: str, wanted_section: str) -> dict[str, str]:
    section = ""
    values = {}
    for raw_line in layout_text.splitlines():
        line = raw_line.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if section == wanted_section and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def _shell_extension_lists(layout_text: str) -> tuple[list[str], list[str]]:
    values = _section_key_values(layout_text, "org/gnome/shell")
    enabled = ast.literal_eval(values["enabled-extensions"])
    disabled = ast.literal_eval(values["disabled-extensions"])
    return enabled, disabled


def test_layout_dumps_do_not_ship_machine_monitor_ids():
    for layout_file in LAYOUT_DIR.glob("*.txt"):
        text = layout_file.read_text()
        for monitor_id in MACHINE_MONITOR_IDS:
            assert monitor_id not in text, f"{layout_file.name} contains {monitor_id}"


def test_dash_to_dock_uses_primary_monitor_template():
    for layout_file in LAYOUT_DIR.glob("*.txt"):
        values = dict(_read_key_values(layout_file.read_text()))
        assert values.get("preferred-monitor-by-connector") == "'primary'"


def test_dash_to_panel_monitor_maps_use_neutral_index():
    for layout_file in LAYOUT_DIR.glob("*.txt"):
        for key, value in _read_key_values(layout_file.read_text()):
            if key not in MONITOR_KEYED_DTP_KEYS:
                continue

            data = json.loads(value.strip().strip("'"))
            assert set(data) in (set(), {"0"}), f"{layout_file.name}:{key} is not neutral"


def test_layout_switcher_helper_is_always_first_and_enabled():
    for layout_file in LAYOUT_DIR.glob("*.txt"):
        enabled, disabled = _shell_extension_lists(layout_file.read_text())
        assert enabled[0] == LAYOUT_SWITCHER_HELPER_UUID
        assert enabled.count(LAYOUT_SWITCHER_HELPER_UUID) == 1
        assert LAYOUT_SWITCHER_HELPER_UUID not in disabled
        assert LEGACY_LAYOUT_SWITCHER_HELPER_UUID not in enabled


def test_unified_runtime_is_the_only_dock_and_panel_extension_enabled():
    for layout_file in LAYOUT_DIR.glob("*.txt"):
        enabled, _disabled = _shell_extension_lists(layout_file.read_text())
        assert RUNTIME_UUID in enabled
        assert COMMUNITY_DOCK_UUID not in enabled
        assert COMMUNITY_PANEL_UUID not in enabled


def test_layouts_use_current_big_shot_and_do_not_require_kiwi():
    for layout_file in LAYOUT_DIR.glob("*.txt"):
        enabled, disabled = _shell_extension_lists(layout_file.read_text())
        assert BIG_SHOT_UUID in enabled
        assert LEGACY_BIG_SHOT_UUID not in enabled
        assert KIWI_UUID not in enabled


def test_no_layout_enables_the_pamac_updates_extension():
    for layout_file in LAYOUT_DIR.glob("*.txt"):
        enabled, _disabled = _shell_extension_lists(layout_file.read_text())
        assert PAMAC_UPDATES_UUID not in enabled


def test_retired_extensions_are_absent_from_layouts_and_dependencies():
    retired = {GSCONNECT_UUID, REMOVABLE_DRIVE_MENU_UUID}
    for layout_file in LAYOUT_DIR.glob("*.txt"):
        text = layout_file.read_text()
        for uuid in retired:
            assert uuid not in text, f"{layout_file.name} still references {uuid}"

    pkgbuild = (REPO_ROOT / "pkgbuild/PKGBUILD").read_text()
    assert "gnome-shell-extension-gsconnect" not in pkgbuild


def test_package_does_not_patch_external_kiwi_installations():
    assert not (REPO_ROOT / "usr/share/layout-switcher/patches/patch-kiwi-focus.sh").exists()
    assert not (REPO_ROOT / "usr/share/libalpm/hooks/zz-layout-switcher-kiwi.hook").exists()


def test_desktop_icon_activation_defaults_are_owned_by_layouts():
    enabled_by_default = {"classic.txt", "hybrid.txt"}
    for layout_file in LAYOUT_DIR.glob("*.txt"):
        text = layout_file.read_text()
        enabled, disabled = _shell_extension_lists(text)

        if layout_file.name in enabled_by_default:
            assert GTK4_DING_UUID in enabled
            assert GTK4_DING_UUID not in disabled
        else:
            assert GTK4_DING_UUID not in enabled
            assert GTK4_DING_UUID in disabled
        assert "[org/gnome/shell/extensions/gtk4-ding]" not in text


def test_copyous_settings_match_biggnome_in_every_layout():
    reference = _section_key_values(
        (LAYOUT_DIR / "biggnome.txt").read_text(),
        COPYOUS_SECTION,
    )

    assert reference == {
        "history-length": "70",
        "open-clipboard-dialog-shortcut": "['<Super>v']",
        "paste-on-copy": "false",
    }
    for layout_file in LAYOUT_DIR.glob("*.txt"):
        values = _section_key_values(layout_file.read_text(), COPYOUS_SECTION)
        assert values == reference, f"{layout_file.name} differs from BigGnome"


def test_original_layouts_reset_accent_to_blue():
    for layout_file in LAYOUT_DIR.glob("*.txt"):
        values = _section_key_values(
            layout_file.read_text(),
            "org/gnome/desktop/interface",
        )
        assert values["accent-color"] == "'blue'"


def test_original_layouts_use_traditional_pointer_scrolling():
    for layout_file in LAYOUT_DIR.glob("*.txt"):
        text = layout_file.read_text()
        mouse = _section_key_values(
            text,
            "org/gnome/desktop/peripherals/mouse",
        )
        touchpad = _section_key_values(
            text,
            "org/gnome/desktop/peripherals/touchpad",
        )
        gdm_mouse = _section_key_values(
            text,
            "io/github/realmazharhussain/GdmSettings/mouse",
        )
        gdm_touchpad = _section_key_values(
            text,
            "io/github/realmazharhussain/GdmSettings/touchpad",
        )

        assert mouse["natural-scroll"] == "false"
        assert touchpad["natural-scroll"] == "false"
        assert gdm_mouse["natural-scrolling"] == "false"
        assert gdm_touchpad["natural-scrolling"] == "false"


def test_fixed_dark_layouts_do_not_require_user_theme():
    for filename in ("biggnome.txt", "desk-ux.txt"):
        text = (LAYOUT_DIR / filename).read_text()
        enabled, disabled = _shell_extension_lists(text)
        user_theme_values = _section_key_values(
            text,
            "org/gnome/shell/extensions/user-theme",
        )

        assert USER_THEME_UUID not in enabled
        assert USER_THEME_UUID in disabled
        assert user_theme_values["name"] == "''"


def test_community_menu_layout_mapping_and_panel_order():
    for filename, menu_layout in COMMUNITY_MENU_LAYOUTS.items():
        text = (LAYOUT_DIR / filename).read_text()
        enabled, disabled = _shell_extension_lists(text)
        menu_values = _section_key_values(
            text,
            "org/gnome/shell/extensions/community-menu",
        )
        dtp_values = _section_key_values(
            text,
            "org/gnome/shell/extensions/dash-to-panel",
        )
        interface_values = _section_key_values(text, "org/gnome/desktop/interface")

        assert menu_values == {
            "desktop-layout": f"'{COMMUNITY_MENU_DESKTOP_LAYOUTS[filename]}'",
            "layout": f"'{menu_layout}'",
        }
        assert dtp_values["hide-overview-on-startup"] == "true"
        assert COMMUNITY_MENU_UUID in enabled
        assert COMMUNITY_MENU_UUID not in disabled
        assert ARCMENU_UUID not in enabled
        assert ARCMENU_UUID in disabled
        assert enabled.index(RUNTIME_UUID) < enabled.index(COMMUNITY_MENU_UUID)
        if filename == "classic.txt":
            assert dtp_values["leftbox-padding"] == "3"
            assert dtp_values["dot-color-override"] == "false"
            assert dtp_values["dot-size"] == "0"
            assert interface_values["icon-theme"] == "'bigicons-papient-light'"
            user_theme_values = _section_key_values(
                text,
                "org/gnome/shell/extensions/user-theme",
            )
            assert user_theme_values["name"] == "''"
            assert USER_THEME_UUID not in enabled
            assert USER_THEME_UUID in disabled
            assert LIGHT_STYLE_UUID in enabled
            assert LIGHT_STYLE_UUID not in disabled
        elif filename == "desk-ux.txt":
            assert interface_values["icon-theme"] == "'bigicons-papient-dark'"
            assert dtp_values["appicon-margin"] == "0"
            assert dtp_values["appicon-padding"] == "2"
            assert dtp_values["leftbox-padding"] == "4"
            assert dtp_values["panel-sizes"] == "'{\"0\":40}'"
            assert dtp_values["dot-style-focused"] == "'METRO'"
            assert dtp_values["dot-style-unfocused"] == "'DASHES'"
            assert dtp_values["focus-highlight"] == "false"
            assert dtp_values["highlight-appicon-hover"] == "false"


def test_hybrid_uses_community_menu_and_compact_panel():
    text = (LAYOUT_DIR / "hybrid.txt").read_text()
    enabled, disabled = _shell_extension_lists(text)
    menu_values = _section_key_values(
        text,
        "org/gnome/shell/extensions/community-menu",
    )
    dtp_values = _section_key_values(
        text,
        "org/gnome/shell/extensions/dash-to-panel",
    )
    shell_values = _section_key_values(text, "org/gnome/shell")
    interface_values = _section_key_values(text, "org/gnome/desktop/interface")

    assert COMMUNITY_MENU_UUID in enabled
    assert COMMUNITY_MENU_UUID not in disabled
    assert ARCMENU_UUID not in enabled
    assert ARCMENU_UUID in disabled
    assert enabled.index(RUNTIME_UUID) < enabled.index(COMMUNITY_MENU_UUID)
    assert menu_values == {
        "desktop-layout": "'Hybrid'",
        "layout": "'MINT'",
    }
    assert interface_values["icon-theme"] == "'bigicons-papient-light'"
    assert USER_THEME_UUID not in enabled
    assert USER_THEME_UUID in disabled
    assert LIGHT_STYLE_UUID in enabled
    assert LIGHT_STYLE_UUID not in disabled
    assert dtp_values["appicon-margin"] == "0"
    assert dtp_values["appicon-padding"] == "1"
    assert dtp_values["panel-sizes"] == "'{\"0\":38}'"
    assert dtp_values["dot-color-override"] == "false"
    panel_size = 38
    app_padding = int(dtp_values["appicon-padding"])
    assert panel_size - (app_padding * 2) == 36
    assert dtp_values["leftbox-padding"] == "0"
    assert "'org.communitybig.ashyterm.desktop'" in shell_values["favorite-apps"]
    assert dtp_values["animate-appicon-hover-animation-type"] == "'SIMPLE'"
    assert "'SIMPLE': uint32 220" in dtp_values["animate-appicon-hover-animation-duration"]
    assert "'SIMPLE': 0.080000000000000002" in dtp_values["animate-appicon-hover-animation-travel"]


def test_normal_layout_switch_uses_only_shell_curtain():
    source = (
        Path(__file__).resolve().parents[1] / "usr/share/layout-switcher/ui/page_layouts.py"
    ).read_text()
    apply_source = source.split("    def _apply(", 1)[1].split("    def _done(", 1)[0]

    assert "begin_loading(" not in apply_source
    assert "show_loading(" not in apply_source
    assert "timeout_add(400" not in apply_source
    assert "icon_from=str(from_icon)" in apply_source
    assert "icon_to=str(to_icon)" in apply_source


def test_layout_confirmation_dialog_uses_wide_horizontal_actions():
    source = (
        Path(__file__).resolve().parents[1] / "usr/share/layout-switcher/ui/page_layouts.py"
    ).read_text()

    assert "_LAYOUT_DIALOG_WIDTH = 520" in source
    assert "d.set_follows_content_size(False)" in source
    assert "d.set_content_width(_LAYOUT_DIALOG_WIDTH)" in source
    assert "actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL" in source
    assert "actions.set_halign(Gtk.Align.END)" in source
    assert 'header_icon.add_css_class("accent")' in source
    assert 'modified.add_css_class("caption-heading")' in source
    assert "body.set_justify(Gtk.Justification.LEFT)" in source
    assert "button.set_size_request(-1, 44)" in source
    assert "set_height_request(" not in source
    assert 'button.add_css_class("suggested-action")' in source
    assert "d.set_default_widget(default_button)" in source


def test_only_desk_ux_uses_floating_panel_geometry():
    for layout_file in LAYOUT_DIR.glob("*.txt"):
        values = _section_key_values(
            layout_file.read_text(),
            "org/gnome/shell/extensions/dash-to-panel",
        )
        if layout_file.name == "desk-ux.txt":
            assert values["panel-side-margins"] == "3"
            assert values["panel-top-bottom-margins"] == "3"
            assert values["global-border-radius"] == "4"
        else:
            assert values.get("panel-side-margins", "0") == "0"
            assert values.get("panel-top-bottom-margins", "0") == "0"


def test_panel_menus_are_disabled_in_shell_native_layouts():
    for filename in NO_PANEL_MENU_LAYOUTS:
        text = (LAYOUT_DIR / filename).read_text()
        enabled, disabled = _shell_extension_lists(text)

        assert COMMUNITY_MENU_UUID not in enabled
        assert COMMUNITY_MENU_UUID in disabled
        assert ARCMENU_UUID not in enabled
        assert ARCMENU_UUID in disabled


def test_minimal_does_not_use_kiwi():
    text = (LAYOUT_DIR / "minimal.txt").read_text()
    enabled, disabled = _shell_extension_lists(text)
    kiwi_values = _section_key_values(text, "org/gnome/shell/extensions/kiwi")

    assert KIWI_UUID not in enabled
    assert KIWI_UUID in disabled
    assert kiwi_values == {}


def test_g_unity_does_not_use_kiwi():
    text = (LAYOUT_DIR / "g-unity.txt").read_text()
    enabled, disabled = _shell_extension_lists(text)
    kiwi_values = _section_key_values(text, "org/gnome/shell/extensions/kiwi")

    assert KIWI_UUID not in enabled
    assert KIWI_UUID in disabled
    assert kiwi_values == {}


def test_no_layout_ships_arcmenu_settings():
    section = "[org/gnome/shell/extensions/arcmenu]"
    for layout_file in LAYOUT_DIR.glob("*.txt"):
        assert section not in layout_file.read_text()
