# SPDX-License-Identifier: MIT
"""Keep the required in-shell layout helper enabled for the user session."""

import logging

from constants import ICON_NAME, migrate_user_data, tr
from extension_update_monitor import ExtensionUpdateMonitor
from helper_client import HELPER_UUID, LEGACY_HELPER_UUID, HelperClient

log = logging.getLogger("big-gnome-center-helper-guard")

class HelperGuard:
    """Monitor only the two Shell lists that can disable the required helper."""

    def __init__(self) -> None:
        from gi.repository import Gio

        self._settings = Gio.Settings.new("org.gnome.shell")
        self._pending_source = 0
        self._legacy_session = False
        self._update_monitor = ExtensionUpdateMonitor()

    def start(self) -> None:
        from gi.repository import GLib

        enabled = set(self._settings.get_strv("enabled-extensions"))
        self._legacy_session = LEGACY_HELPER_UUID in enabled and HELPER_UUID not in enabled
        if not self._legacy_session:
            ok, changed, info = HelperClient.ensure_enabled()
            if not ok:
                log.warning("initial helper repair failed: %s", info)
            elif changed:
                self._notify_repair()

        self._settings.connect("changed::enabled-extensions", self._on_settings_changed)
        self._settings.connect("changed::disabled-extensions", self._on_settings_changed)
        self._update_monitor.start()
        self._loop = GLib.MainLoop()
        try:
            self._loop.run()
        finally:
            self._update_monitor.stop()

    def _on_settings_changed(self, settings, key: str) -> None:
        from gi.repository import GLib

        if self._pending_source:
            return
        self._pending_source = GLib.timeout_add(80, self._repair)

    def _repair(self) -> bool:
        self._pending_source = 0
        if self._legacy_session:
            enabled = set(self._settings.get_strv("enabled-extensions"))
            if HELPER_UUID not in enabled:
                return False
            self._legacy_session = False
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
                    "Big Gnome Center",
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
    migrate_user_data()
    logging.basicConfig(level=logging.WARNING)
    HelperGuard().start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
