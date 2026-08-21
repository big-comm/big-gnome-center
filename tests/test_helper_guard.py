# SPDX-License-Identifier: MIT
"""Static checks for the required helper session guard."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTOSTART = ROOT / "etc/xdg/autostart/org.communitybig.layout-switcher-helper-guard.desktop"


def test_guard_autostart_uses_modern_gnome_session_path():
    desktop = AUTOSTART.read_text()

    assert "Exec=/usr/bin/layout-switcher-helper-guard" in desktop
    assert "OnlyShowIn=GNOME;" in desktop
    assert "X-GNOME-Autostart-enabled=true" in desktop
    assert "X-GNOME-Autostart-Phase" not in desktop


def test_guard_launcher_is_executable():
    launcher = ROOT / "usr/bin/layout-switcher-helper-guard"

    assert launcher.stat().st_mode & 0o111
    assert "helper_guard.py" in launcher.read_text()


def test_guard_starts_background_extension_update_monitor():
    source = (ROOT / "usr/share/layout-switcher/helper_guard.py").read_text()
    desktop = (ROOT / "usr/share/applications/org.communitybig.layout-switcher.desktop").read_text()

    assert "ExtensionUpdateMonitor" in source
    assert "self._update_monitor.start()" in source
    assert "X-GNOME-UsesNotifications=true" in desktop


def test_guard_migrates_owned_extension_uuids_at_session_start():
    client = (ROOT / "usr/share/layout-switcher/helper_client.py").read_text()
    guard = (ROOT / "usr/share/layout-switcher/helper_guard.py").read_text()

    assert "LEGACY_COMMUNITY_MENU_UUID" in client
    assert "LEGACY_BIG_SHOT_UUID" in client
    assert "LEGACY_DASH_TO_DOCK_UUID" in client
    assert "LEGACY_DASH_TO_PANEL_UUID" in client
    assert "LAYOUT_COMPONENT_UUID_MIGRATIONS" in client
    assert "required_helper_lists(enabled, disabled)" in client
    assert "_migrate_initial_session" in guard
    assert "HelperClient.ensure_available()" in guard
    assert "HelperClient.apply_layout(" in guard
    assert "reload=reload_uuids" in guard
    assert "LEGACY_DASH_TO_PANEL_UUID" in guard
    assert "available_uuids=HelperClient.installed_extension_uuids()" in guard
    assert "_migrate_arcmenu_icon_path" in guard
    assert "HelperClient.migrate_component_asset_path(current)" in guard
    assert "HelperClient.reload_extension(_ARCMENU_UUID)" in guard


def test_package_upgrade_retires_legacy_helper_directory():
    install_script = (ROOT / "pkgbuild/pkgbuild.install").read_text()

    assert (
        "/usr/share/gnome-shell/extensions/layout-switcher-helper@bigcommunity.org"
    ) in install_script
    assert "retire_legacy_helper" in install_script
    assert "post_install()" in install_script
    assert "post_upgrade()" in install_script


def test_only_current_helper_directory_is_shipped():
    extensions = ROOT / "usr/share/gnome-shell/extensions"

    assert (extensions / "layout-switcher-helper@communitybig.org").is_dir()
    assert not (extensions / "layout-switcher-helper@bigcommunity.org").exists()


def test_package_upgrade_retires_legacy_community_menu_directory():
    install_script = (ROOT / "pkgbuild/pkgbuild.install").read_text()

    assert ("/usr/share/gnome-shell/extensions/community-menu@bigcommunity.org") in install_script
    assert "retire_legacy_community_menu" in install_script


def test_only_current_community_menu_directory_is_shipped():
    extensions = ROOT / "usr/share/gnome-shell/extensions"

    assert (extensions / "community-menu@communitybig.org").is_dir()
    assert not (extensions / "community-menu@bigcommunity.org").exists()
