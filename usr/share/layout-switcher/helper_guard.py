# SPDX-License-Identifier: MIT
"""Keep the required in-shell layout helper enabled for the user session."""

import logging
from pathlib import Path

from constants import ICON_NAME, tr
from extension_update_monitor import ExtensionUpdateMonitor
from helper_client import (
    COMMUNITY_PANEL_UUID,
    LEGACY_DASH_TO_DOCK_UUID,
    LEGACY_DASH_TO_PANEL_UUID,
    HelperClient,
)

log = logging.getLogger("layout-switcher-helper-guard")

_ARCMENU_UUID = "arcmenu@arcmenu.com"


class HelperGuard:
    """Monitor only the two Shell lists that can disable the required helper."""

    def __init__(self) -> None:
        from gi.repository import Gio

        self._settings = Gio.Settings.new("org.gnome.shell")
        self._pending_source = 0
        self._update_monitor = ExtensionUpdateMonitor()

    def start(self) -> None:
        from gi.repository import GLib

        changed = self._migrate_initial_session()
        if changed:
            self._notify_repair()

        self._settings.connect("changed::enabled-extensions", self._on_settings_changed)
        self._settings.connect("changed::disabled-extensions", self._on_settings_changed)
        self._update_monitor.start()
        self._loop = GLib.MainLoop()
        try:
            self._loop.run()
        finally:
            self._update_monitor.stop()

    def _migrate_initial_session(self) -> bool:
        """Move legacy components only after the new helper is live."""
        from gi.repository import Gio

        enabled_before = list(self._settings.get_strv("enabled-extensions"))
        disabled_before = list(self._settings.get_strv("disabled-extensions"))

        ok, helper_changed, info = HelperClient.ensure_enabled()
        if not ok:
            log.warning("initial helper repair failed: %s", info)
            return False

        helper_ok, helper_info = HelperClient.ensure_available()
        if not helper_ok:
            log.warning("initial helper start failed: %s", helper_info)
            return helper_changed

        enabled_target, disabled_target = HelperClient.required_extension_lists(
            enabled_before,
            disabled_before,
            available_uuids=HelperClient.installed_extension_uuids(),
        )
        icon_changed = self._migrate_arcmenu_icon_path()
        enabled_current = list(self._settings.get_strv("enabled-extensions"))
        disabled_current = list(self._settings.get_strv("disabled-extensions"))
        if enabled_current == enabled_target and disabled_current == disabled_target:
            if icon_changed and _ARCMENU_UUID in enabled_target:
                HelperClient.reload_extension(_ARCMENU_UUID)
            return helper_changed or icon_changed

        reload_uuids = [_ARCMENU_UUID] if _ARCMENU_UUID in enabled_target else []
        apply_ok, apply_info = HelperClient.apply_layout(
            enabled_target,
            reload=reload_uuids,
            teardown=[LEGACY_DASH_TO_DOCK_UUID, LEGACY_DASH_TO_PANEL_UUID],
        )
        if not apply_ok:
            log.warning("initial component migration failed: %s", apply_info)
            return helper_changed

        if disabled_current != disabled_target:
            self._settings.set_strv("disabled-extensions", disabled_target)
        if enabled_current != enabled_target:
            self._settings.set_strv("enabled-extensions", enabled_target)
        Gio.Settings.sync()
        log.info("initial component migration completed: %s", apply_info)
        return True

    @staticmethod
    def _migrate_arcmenu_icon_path() -> bool:
        """Move ArcMenu's custom button icon away from the retired UUID path."""
        try:
            from gi.repository import Gio

            settings = Gio.Settings.new("org.gnome.shell.extensions.arcmenu")
            current = settings.get_string("menu-button-icon")
            migrated = HelperClient.migrate_component_asset_path(current)
            if migrated == current or not Path(migrated).is_file():
                return False
            settings.set_string("menu-button-icon", migrated)
            Gio.Settings.sync()
            return True
        except Exception as exc:
            log.warning("ArcMenu icon migration failed: %s", exc)
            return False

    def _on_settings_changed(self, settings, key: str) -> None:
        from gi.repository import GLib

        if self._pending_source:
            return
        self._pending_source = GLib.timeout_add(80, self._repair)

    def _repair(self) -> bool:
        self._pending_source = 0
        ok, changed, info = HelperClient.ensure_enabled()
        if not ok:
            log.warning("helper repair failed: %s", info)
        elif changed:
            self._notify_repair()
        return False

    @staticmethod
    def _notify_repair() -> None:
        """Use the desktop notification D-Bus API without a libnotify dependency."""
        try:
            from gi.repository import Gio, GLib

            proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.NONE,
                None,
                "org.freedesktop.Notifications",
                "/org/freedesktop/Notifications",
                "org.freedesktop.Notifications",
                None,
            )
            args = GLib.Variant(
                "(susssasa{sv}i)",
                (
                    "Layout Switcher",
                    0,
                    ICON_NAME,
                    tr("Layout helper restored"),
                    tr("The required layout helper was re-enabled automatically."),
                    [],
                    {},
                    5000,
                ),
            )
            proxy.call_sync("Notify", args, Gio.DBusCallFlags.NONE, 3000, None)
        except Exception as exc:
            log.debug("notification failed: %s", exc)


def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    HelperGuard().start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
