# SPDX-License-Identifier: MIT
"""Tests for session-level extension update notifications."""

import concurrent.futures
from unittest.mock import patch

from constants import tr
from extension_update_monitor import ExtensionUpdateMonitor
from update_checker import UpdateInfo


class FakeSettings:
    def __init__(self, values=None):
        self.values = values if values is not None else {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value

    def delete(self, key):
        self.values.pop(key, None)


class FakeNotifier:
    def __init__(self):
        self.calls = []

    def start(self):
        return True

    def notify(self, title, body, actions, context=None):
        self.calls.append((title, body, actions, context))
        return len(self.calls)


def _updates():
    return {
        "cube@example.org": UpdateInfo(
            uuid="cube@example.org",
            current_version=4,
            latest_version=5,
            ego_id=10,
        ),
        "lamp@example.org": UpdateInfo(
            uuid="lamp@example.org",
            current_version=2,
            latest_version=3,
            ego_id=20,
        ),
    }


def _monitor(settings, notifier=None):
    return ExtensionUpdateMonitor(
        settings_factory=lambda: settings,
        notifier=notifier or FakeNotifier(),
    )


def _shutdown(monitor):
    monitor._executor.shutdown(wait=True, cancel_futures=True)


def test_available_updates_emit_native_notification_once():
    settings = FakeSettings()
    notifier = FakeNotifier()
    monitor = _monitor(settings, notifier)

    monitor._handle_updates(_updates(), settings)
    monitor._handle_updates(_updates(), settings)

    assert len(notifier.calls) == 1
    title, body, actions, context = notifier.calls[0]
    assert title == tr("Extension updates available")
    assert "cube" in body
    assert "lamp" in body
    assert {action_id for action_id, label in actions} == {
        "default",
        "view",
        "update-all",
    }
    assert set(context) == set(_updates())
    _shutdown(monitor)


def test_no_updates_clear_notification_deduplication():
    settings = FakeSettings({"ext_update_notification_signature": "old:2"})
    monitor = _monitor(settings)

    monitor._handle_updates({}, settings)

    assert "ext_update_notification_signature" not in settings.values
    _shutdown(monitor)


def test_auto_update_is_opt_in_and_skips_available_notification():
    settings = FakeSettings({"ext_auto_update": True})
    notifier = FakeNotifier()
    monitor = _monitor(settings, notifier)

    with patch.object(monitor, "_queue_apply") as mock_apply:
        monitor._handle_updates(_updates(), settings)

    mock_apply.assert_called_once()
    assert notifier.calls == []
    _shutdown(monitor)


def test_notification_actions_open_or_apply_updates():
    settings = FakeSettings()
    monitor = _monitor(settings)
    updates = _updates()

    with (
        patch.object(monitor, "_open_updates") as mock_open,
        patch.object(monitor, "_queue_apply") as mock_apply,
    ):
        monitor._on_notification_action("view", updates)
        monitor._on_notification_action("update-all", updates)

    mock_open.assert_called_once_with()
    mock_apply.assert_called_once_with(updates)
    _shutdown(monitor)


def test_successful_background_apply_emits_completion_notification():
    settings = FakeSettings()
    notifier = FakeNotifier()
    monitor = _monitor(settings, notifier)
    info = next(iter(_updates().values()))
    future = concurrent.futures.Future()
    future.set_result([(info, True, "")])

    monitor._finish_apply(future)

    assert notifier.calls[0][0] == tr("Extension updates installed")
    assert "cube" in notifier.calls[0][1]
    _shutdown(monitor)


def test_background_apply_exception_offers_retry():
    settings = FakeSettings()
    notifier = FakeNotifier()
    monitor = _monitor(settings, notifier)
    future = concurrent.futures.Future()
    future.set_exception(RuntimeError("download failed"))

    monitor._finish_apply(future, _updates())

    title, body, actions, context = notifier.calls[0]
    assert title == tr("Some extension updates failed")
    assert "cube" in body
    assert "lamp" in body
    assert ("update-all", tr("Try again")) in actions
    assert set(context) == set(_updates())
    _shutdown(monitor)
