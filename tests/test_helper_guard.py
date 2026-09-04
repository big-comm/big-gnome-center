# SPDX-License-Identifier: MIT
"""Static checks for the required helper session guard."""

import sys
from pathlib import Path

from constants import DESKTOP_ID, LEGACY_DESKTOP_ID, _replace_legacy_desktop_id

ROOT = Path(__file__).resolve().parents[1]
AUTOSTART = ROOT / "etc/xdg/autostart/br.com.biglinux.BigGnomeCenter-helper-guard.desktop"


def test_package_check_does_not_create_python_bytecode():
    assert sys.dont_write_bytecode


def test_guard_autostart_uses_modern_gnome_session_path():
    desktop = AUTOSTART.read_text()

    assert "Exec=/usr/bin/big-gnome-center-helper-guard" in desktop
    assert "OnlyShowIn=GNOME;" in desktop
    assert "X-GNOME-Autostart-enabled=true" in desktop
    assert "X-GNOME-Autostart-Phase" not in desktop


def test_guard_launcher_is_executable():
    launcher = ROOT / "usr/bin/big-gnome-center-helper-guard"

    assert launcher.stat().st_mode & 0o111
    assert "helper_guard.py" in launcher.read_text()


def test_legacy_guard_command_points_to_rebranded_launcher():
    launcher = ROOT / "usr/bin/layout-switcher-helper-guard"

    assert launcher.is_symlink()
    assert launcher.resolve().name == "big-gnome-center-helper-guard"


def test_guard_starts_background_extension_update_monitor():
    source = (ROOT / "usr/share/big-gnome-center/helper_guard.py").read_text()
    desktop = (ROOT / "usr/share/applications/br.com.biglinux.BigGnomeCenter.desktop").read_text()

    assert "ExtensionUpdateMonitor" in source
    assert "self._update_monitor.start()" in source
    assert "X-GNOME-UsesNotifications=true" in desktop


def test_rebrand_migrates_settings_folder_launcher_id():
    apps = ["org.gnome.Settings.desktop", LEGACY_DESKTOP_ID, DESKTOP_ID]

    assert _replace_legacy_desktop_id(apps) == [
        "org.gnome.Settings.desktop",
        DESKTOP_ID,
    ]


def test_guard_preserves_layout_components_at_session_start():
    client = (ROOT / "usr/share/big-gnome-center/helper_client.py").read_text()
    guard = (ROOT / "usr/share/big-gnome-center/helper_guard.py").read_text()

    assert "LEGACY_HELPER_UUID in enabled and HELPER_UUID not in enabled" in guard
    assert "if not self._legacy_session:" in guard
    assert "HelperClient.ensure_enabled()" in guard
    assert "HelperClient.required_extension_lists(" not in guard
    assert "HelperClient.apply_layout(" not in guard
    assert "_migrate_arcmenu_icon_path" not in guard

    # Explicit layout application still owns legacy component migration.
    assert "LEGACY_COMMUNITY_MENU_UUID" in client
    assert "LEGACY_BIG_SHOT_UUID" in client
    assert "LEGACY_DASH_TO_DOCK_UUID" in client
    assert "LEGACY_DASH_TO_PANEL_UUID" in client
    assert "LAYOUT_COMPONENT_UUID_MIGRATIONS" in client
    assert "required_helper_lists(enabled, disabled)" in client


def test_package_upgrade_preserves_legacy_helper_directory():
    install_script = (ROOT / "pkgbuild/pkgbuild.install").read_text()

    assert "retire_legacy_helper" not in install_script


def test_current_and_legacy_helper_directories_are_shipped():
    extensions = ROOT / "usr/share/gnome-shell/extensions"

    assert (extensions / "layout-switcher-helper@communitybig.org").is_dir()
    legacy = extensions / "layout-switcher-helper@bigcommunity.org"
    assert legacy.is_dir()
    metadata = (legacy / "metadata.json").read_text()
    assert '"uuid": "layout-switcher-helper@bigcommunity.org"' in metadata


def test_package_upgrade_preserves_legacy_community_menu_directory():
    install_script = (ROOT / "pkgbuild/pkgbuild.install").read_text()

    assert "retire_legacy_community_menu" not in install_script


def test_current_and_legacy_community_menu_directories_are_shipped():
    extensions = ROOT / "usr/share/gnome-shell/extensions"

    assert (extensions / "community-menu@communitybig.org").is_dir()
    assert (extensions / "community-menu@bigcommunity.org").is_dir()
    metadata = (extensions / "community-menu@bigcommunity.org/metadata.json").read_text()
    assert '"uuid": "community-menu@bigcommunity.org"' in metadata
