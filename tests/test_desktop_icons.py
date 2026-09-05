# SPDX-License-Identifier: MIT
"""Desktop icon integration contracts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_desktop_page_exposes_global_desktop_icons_control():
    source = (ROOT / "usr/share/big-gnome-center/ui/page_desktop.py").read_text()

    assert "DesktopIconsControls" in source
    assert "self._desktop_icons.refresh()" in source


def test_desktop_navigation_uses_a_monochrome_display_icon():
    source = (ROOT / "usr/share/big-gnome-center/ui/window.py").read_text()

    assert '("desktop", tr("Desktop"), "video-display-symbolic")' in source
    assert "preferences-desktop-symbolic" not in source


def test_effects_page_does_not_duplicate_desktop_icons_control():
    source = (ROOT / "usr/share/big-gnome-center/ui/page_effects.py").read_text()

    assert "DesktopIconsControls" not in source


def test_desktop_page_exposes_global_menu_and_super_controls():
    source = (ROOT / "usr/share/big-gnome-center/ui/page_desktop.py").read_text()

    assert '"community_menu_enabled"' in source
    assert '"super_key_opens_menu"' in source
    assert "COMMUNITY_MENU_UUID" in source
    assert "SUPER_KEY_PATH" in source


def test_community_menu_controls_are_limited_to_supported_layouts():
    source = (ROOT / "usr/share/big-gnome-center/ui/page_desktop.py").read_text()

    assert '"Classic": "APPS_ONLY"' in source
    assert '"Desk UX": "APP_GRID"' in source
    assert '"Hybrid": "MINT"' in source
    assert "self._shell_group.set_visible(supports_menu)" in source


def test_community_menu_exposes_three_visual_style_choices():
    source = (ROOT / "usr/share/big-gnome-center/ui/page_desktop.py").read_text()

    assert '("Classic", "APPS_ONLY"' in source
    assert '("Desk-UX", "APP_GRID"' in source
    assert '("Hybrid", "MINT"' in source
    assert 'tr("Menu style")' in source
    assert 'tr("Default")' in source
    assert "MENU_LAYOUT_PATH" in source


def test_community_menu_previews_match_each_layout_geometry():
    source = (ROOT / "usr/share/big-gnome-center/ui/page_desktop.py").read_text()

    assert "_append_classic_preview" in source
    assert "_append_desk_ux_preview" in source
    assert "_append_hybrid_preview" in source
    assert "stage.set_size_request(-1, 120)" in source
    assert "preview.set_size_request(78, 108)" in source
    assert "preview.set_size_request(132, 108)" in source
    assert "preview.set_size_request(146, 108)" in source


def test_community_menu_default_badge_does_not_resize_the_preview_card():
    source = (ROOT / "usr/share/big-gnome-center/ui/page_desktop.py").read_text()

    assert "overlay = Gtk.Overlay()" in source
    assert "overlay.set_child(box)" in source
    assert "overlay.add_overlay(badge)" in source
    assert "button.set_child(overlay)" in source
    assert "card.append(badge)" not in source
    assert "box.append(badge)" not in source
    assert "badge.set_visible(False)" in source
    assert "badge.set_visible(value == default_style)" in source


def test_hybrid_preview_uses_aligned_compact_rail_and_left_actions():
    source = (ROOT / "usr/share/big-gnome-center/ui/page_desktop.py").read_text()

    assert "rail_width = 27" in source
    assert 'self._preview_block("menu-style-user", rail_width, 7)' in source
    assert "self._build_preview_categories(6, width=rail_width)" in source
    assert "actions.set_halign(Gtk.Align.END if user else Gtk.Align.START)" in source
    assert "actions.set_hexpand(user)" in source
    assert 'self._preview_block("menu-style-divider", 18, 1)' not in source


def test_community_menu_default_badge_is_translucent():
    source = (ROOT / "usr/share/big-gnome-center/ui/styles.py").read_text()

    assert "background-color: alpha(@accent_bg_color, 0.50);" in source


def test_desktop_page_exposes_six_visual_notification_positions():
    source = (ROOT / "usr/share/big-gnome-center/ui/page_desktop.py").read_text()

    for value in (
        "top-center",
        "bottom-center",
        "top-right",
        "top-left",
        "bottom-left",
        "bottom-right",
    ):
        assert f'("{value}", tr(' in source

    assert 'title=tr("Notification position")' in source
    assert "_build_notification_position_preview" in source
    assert 'add_css_class("notification-position-card")' in source
    assert "set_min_children_per_line(3)" in source
    assert "set_max_children_per_line(3)" in source


def test_notification_position_defaults_are_layout_specific():
    source = (ROOT / "usr/share/big-gnome-center/ui/page_desktop.py").read_text()

    assert '"Classic": "bottom-right"' in source
    assert '"Hybrid": "bottom-right"' in source
    assert '"Desk UX": "bottom-right"' in source
    assert '"Minimal": "top-center"' in source
    assert '"BigGnome": "top-center"' in source
    assert '"G-Unity": "top-right"' in source
    assert 'self._prefs.get("notification_positions", {})' in source


def test_notification_selection_applies_then_sends_a_real_preview():
    source = (ROOT / "usr/share/big-gnome-center/ui/page_desktop.py").read_text()

    apply_index = source.index("HelperClient.set_notification_position(value)")
    persist_index = source.index('self._save_preference("notification_positions", saved)')
    preview_index = source.index("GLib.timeout_add(200, self._send_notification_preview)")
    assert apply_index < persist_index < preview_index
    assert 'Gio.Notification.new(tr("Notification preview"))' in source
    assert 'notification.set_body(tr("Notifications will appear here."))' in source
    assert 'app.send_notification("notification-position-preview", notification)' in source


def test_notification_choices_are_reenabled_after_each_request():
    source = (ROOT / "usr/share/big-gnome-center/ui/page_desktop.py").read_text()

    assert "self._notification_flow.set_sensitive(False)" in source
    assert "self._notification_flow.set_sensitive(True)" in source
    assert source.index("self._notification_flow.set_sensitive(True)") < source.index(
        "supports_menu = self._active_layout in MENU_LAYOUT_DEFAULTS"
    )


def test_gtk4_ding_dependency_is_retained():
    pkgbuild = (ROOT / "pkgbuild/PKGBUILD").read_text()

    assert "gnome-shell-extension-gtk4-desktop-icons-ng" in pkgbuild


def test_obsolete_desktop_icons_ng_card_is_not_featured():
    constants = (ROOT / "usr/share/big-gnome-center/constants.py").read_text()

    assert "ding@rastersoft.com" not in constants
