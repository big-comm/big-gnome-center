# SPDX-License-Identifier: MIT
"""Check extension updates in the user session and emit native notifications."""

import concurrent.futures
import logging
import subprocess
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional

import update_checker
from constants import ICON_NAME, UPDATE_CHECK_INTERVAL, tr
from settings_store import Settings

log = logging.getLogger("layout-switcher-extension-updates")

_LOGIN_CHECK_DELAY = 60
_NOTIFICATION_SIGNATURE_KEY = "ext_update_notification_signature"


class NativeNotifier:
    """Small org.freedesktop.Notifications client with action dispatch."""

    def __init__(self, action_cb: Callable[[str, Dict], None]) -> None:
        self._action_cb = action_cb
        self._proxy = None
        self._contexts: Dict[int, Dict] = {}

    def start(self) -> bool:
        if self._proxy is not None:
            return True
        try:
            from gi.repository import Gio

            self._proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.NONE,
                None,
                "org.freedesktop.Notifications",
                "/org/freedesktop/Notifications",
                "org.freedesktop.Notifications",
                None,
            )
            self._proxy.connect("g-signal", self._on_signal)
            return True
        except Exception as exc:
            log.debug("notification proxy unavailable: %s", exc)
            self._proxy = None
            return False

    def notify(
        self,
        title: str,
        body: str,
        actions: Iterable[tuple[str, str]],
        context: Optional[Dict] = None,
    ) -> int:
        if not self.start():
            return 0
        try:
            from gi.repository import Gio, GLib

            flat_actions = []
            for action_id, label in actions:
                flat_actions.extend((action_id, label))
            args = GLib.Variant(
                "(susssasa{sv}i)",
                (
                    "Layout Switcher",
                    0,
                    ICON_NAME,
                    title,
                    body,
                    flat_actions,
                    {},
                    -1,
                ),
            )
            result = self._proxy.call_sync(
                "Notify",
                args,
                Gio.DBusCallFlags.NONE,
                3000,
                None,
            )
            notification_id = int(result.unpack()[0])
            self._contexts[notification_id] = dict(context or {})
            return notification_id
        except Exception as exc:
            log.debug("notification failed: %s", exc)
            return 0

    def _on_signal(self, proxy, sender_name, signal_name: str, parameters) -> None:
        values = parameters.unpack()
        if signal_name == "NotificationClosed" and values:
            self._contexts.pop(int(values[0]), None)
            return
        if signal_name != "ActionInvoked" or len(values) < 2:
            return
        notification_id = int(values[0])
        action = str(values[1])
        context = self._contexts.pop(notification_id, {})
        self.close(notification_id)
        self._action_cb(action, context)

    def close(self, notification_id: int) -> None:
        if self._proxy is None or notification_id <= 0:
            return
        try:
            from gi.repository import Gio, GLib

            self._proxy.call(
                "CloseNotification",
                GLib.Variant("(u)", (notification_id,)),
                Gio.DBusCallFlags.NONE,
                3000,
                None,
                None,
            )
        except Exception:
            pass


class ExtensionUpdateMonitor:
    """Run update checks independently from the application window."""

    def __init__(
        self,
        *,
        settings_factory: Callable[[], Settings] = Settings,
        notifier=None,
        check_func: Callable = update_checker.check_all,
        apply_func: Callable = update_checker.apply_all,
    ) -> None:
        self._settings_factory = settings_factory
        self._check_func = check_func
        self._apply_func = apply_func
        self._notifier = notifier or NativeNotifier(self._on_notification_action)
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="cls-ext-updates",
        )
        self._checking = False
        self._applying = False
        self._source_ids: list[int] = []

    def start(self) -> None:
        from gi.repository import GLib

        self._notifier.start()
        self._source_ids.append(GLib.timeout_add_seconds(_LOGIN_CHECK_DELAY, self._initial_check))
        self._source_ids.append(
            GLib.timeout_add_seconds(UPDATE_CHECK_INTERVAL, self._periodic_check)
        )

    def stop(self) -> None:
        try:
            from gi.repository import GLib

            for source_id in self._source_ids:
                GLib.source_remove(source_id)
        except Exception:
            pass
        self._source_ids.clear()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _initial_check(self) -> bool:
        self._check_if_due()
        return False

    def _periodic_check(self) -> bool:
        self._check_if_due()
        return True

    def _check_if_due(self) -> None:
        settings = self._settings_factory()
        if update_checker.time_since_last_check(settings) >= UPDATE_CHECK_INTERVAL:
            self._queue_check()

    def _queue_check(self) -> None:
        if self._checking:
            return
        self._checking = True
        future = self._executor.submit(self._check_func, force_refresh=True)
        future.add_done_callback(self._dispatch_check_result)

    def _dispatch_check_result(self, future) -> None:
        from gi.repository import GLib

        GLib.idle_add(self._finish_check, future)

    def _finish_check(self, future) -> bool:
        self._checking = False
        try:
            updates = future.result()
        except Exception as exc:
            log.debug("background update check failed: %s", exc)
            return False

        settings = self._settings_factory()
        update_checker.mark_checked(settings)
        self._handle_updates(dict(updates or {}), settings)
        return False

    @staticmethod
    def _signature(updates: Dict[str, update_checker.UpdateInfo]) -> str:
        return "|".join(f"{uuid}:{updates[uuid].latest_version}" for uuid in sorted(updates))

    @staticmethod
    def _display_names(updates: Dict[str, update_checker.UpdateInfo]) -> str:
        names = [uuid.split("@", 1)[0] for uuid in sorted(updates)]
        if len(names) > 4:
            names = names[:4] + ["…"]
        return ", ".join(names)

    def _handle_updates(self, updates: Dict, settings=None) -> None:
        settings = settings or self._settings_factory()
        if not updates:
            settings.delete(_NOTIFICATION_SIGNATURE_KEY)
            return

        signature = self._signature(updates)
        if settings.get(_NOTIFICATION_SIGNATURE_KEY, "") == signature:
            return

        settings.set(_NOTIFICATION_SIGNATURE_KEY, signature)
        if settings.get("ext_auto_update", False):
            self._queue_apply(updates)
            return

        notification_id = self._notifier.notify(
            tr("Extension updates available"),
            tr("Available updates: {names}").format(names=self._display_names(updates)),
            [
                ("default", tr("View updates")),
                ("view", tr("View updates")),
                ("update-all", tr("Update all")),
            ],
            updates,
        )
        if notification_id <= 0:
            settings.delete(_NOTIFICATION_SIGNATURE_KEY)

    def _on_notification_action(self, action: str, updates: Dict) -> None:
        if action in {"default", "view"}:
            self._open_updates()
        elif action == "update-all" and updates:
            self._queue_apply(updates)

    @staticmethod
    def _open_updates() -> None:
        launcher = Path("/usr/bin/layout-switcher")
        argv = [str(launcher) if launcher.exists() else "layout-switcher"]
        argv.append("--extensions-updates")
        try:
            subprocess.Popen(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                start_new_session=True,
            )
        except OSError as exc:
            log.debug("could not open update page: %s", exc)

    def _queue_apply(self, updates: Dict) -> None:
        if self._applying:
            return
        self._applying = True
        future = self._executor.submit(self._apply_func, list(updates.values()))
        future.add_done_callback(lambda done: self._dispatch_apply_result(done, updates))

    def _dispatch_apply_result(self, future, requested: Dict) -> None:
        from gi.repository import GLib

        GLib.idle_add(self._finish_apply, future, requested)

    def _finish_apply(self, future, requested: Optional[Dict] = None) -> bool:
        self._applying = False
        try:
            results = future.result()
        except Exception as exc:
            log.debug("background update apply failed: %s", exc)
            failed = dict(requested or {})
            self._notify_apply_failure({}, failed)
            return False

        succeeded = {info.uuid: info for info, ok, msg in results if ok}
        failed = {info.uuid: info for info, ok, msg in results if not ok}
        if failed:
            self._notify_apply_failure(succeeded, failed)
            return False

        self._notifier.notify(
            tr("Extension updates installed"),
            tr("Updated: {names}").format(names=self._display_names(succeeded)),
            [
                ("default", tr("View extensions")),
                ("view", tr("View extensions")),
            ],
            {},
        )
        return False

    def _notify_apply_failure(self, succeeded: Dict, failed: Dict) -> None:
        body_parts = []
        if succeeded:
            body_parts.append(tr("Updated: {names}").format(names=self._display_names(succeeded)))
        if failed:
            body_parts.append(tr("Failed: {names}").format(names=self._display_names(failed)))
        self._notifier.notify(
            tr("Some extension updates failed"),
            "\n".join(body_parts),
            [
                ("default", tr("View updates")),
                ("view", tr("View updates")),
                ("update-all", tr("Try again")),
            ],
            failed,
        )
