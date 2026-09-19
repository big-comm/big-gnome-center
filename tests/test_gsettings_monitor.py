# SPDX-License-Identifier: MIT
"""Monitor validation, Gio read-after-connect contract and callback lifetime."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from settings_store import GSettingsMonitor


class SignalSettings:
    def __init__(self):
        self.callbacks = {}
        self.history = []
        self.reads = []
        self.disconnected = []
        self.fail_read = None
        self.fail_disconnect = False
        self.emit_during_read = False

    def connect(self, signal, callback):
        handler = len(self.history) + 1
        self.callbacks[handler] = (signal, callback)
        self.history.append(callback)
        return handler

    def get_value(self, key):
        assert self.callbacks, "Keys must be read after connecting"
        if self.emit_during_read:
            for signal, callback in list(self.callbacks.values()):
                callback(self, key)
        if key == self.fail_read:
            raise RuntimeError("injected read failure")
        self.reads.append(key)
        return object()

    def emit(self, key):
        if key in self.reads:
            for signal, callback in list(self.callbacks.values()):
                if signal in {"changed", f"changed::{key}"}:
                    callback(self, key)

    def disconnect(self, handler):
        self.disconnected.append(handler)
        if self.fail_disconnect:
            raise RuntimeError("injected disconnect failure")
        del self.callbacks[handler]


@pytest.fixture
def monitor():
    monitor = GSettingsMonitor()
    definition = Mock()
    definition.get_path.return_value = "/org/example/monitor/"
    definition.has_key.side_effect = lambda key: key in {"text", "enabled"}
    definition.list_keys.return_value = ["text", "enabled"]
    source = Mock()
    source.lookup.return_value = definition
    created = []

    def create(*args):
        assert args == (definition, None, None)
        settings = SignalSettings()
        created.append(settings)
        return settings

    gio = SimpleNamespace(
        SettingsSchemaSource=SimpleNamespace(get_default=Mock(return_value=source)),
        Settings=SimpleNamespace(new_full=Mock(side_effect=create)),
    )
    monitor._Gio = gio
    yield SimpleNamespace(monitor=monitor, definition=definition, source=source,
                          gio=gio, created=created)
    monitor.disconnect_all()


@pytest.mark.parametrize("any_key", [False, True])
@pytest.mark.parametrize("invalid", ["source", "schema", "path", "callback"])
def test_rejects_invalid_registration_before_construction(monitor, any_key, invalid):
    callback = Mock()
    if invalid == "source":
        monitor.gio.SettingsSchemaSource.get_default.return_value = None
    elif invalid == "schema":
        monitor.source.lookup.return_value = None
    elif invalid == "path":
        monitor.definition.get_path.return_value = None
    else:
        callback = None
    target = monitor.monitor
    assert not (target.watch_any("test", callback) if any_key else
                target.watch("test", "text", callback))
    monitor.gio.Settings.new_full.assert_not_called()
    assert target._watchers == []


@pytest.mark.parametrize("schema", [None, "", 1, "embedded\0nul"])
def test_rejects_invalid_schema_identifiers(monitor, schema):
    assert not monitor.monitor.watch(schema, "text", Mock())
    assert not monitor.monitor.watch_any(schema, Mock())
    monitor.gio.SettingsSchemaSource.get_default.assert_not_called()


@pytest.mark.parametrize("key", [None, "", 1, "embedded\0nul", "unknown"])
def test_rejects_invalid_keys_before_construction(monitor, key):
    assert not monitor.monitor.watch("test", key, Mock())
    monitor.gio.Settings.new_full.assert_not_called()


@pytest.mark.parametrize("any_key", [False, True])
def test_primes_connected_keys_without_initial_callback(monitor, any_key):
    settings = SignalSettings()
    settings.emit_during_read = True
    monitor.gio.Settings.new_full.side_effect = None
    monitor.gio.Settings.new_full.return_value = settings
    callback = Mock()
    target = monitor.monitor
    assert (target.watch_any("test", callback) if any_key else
            target.watch("test", "text", callback))
    assert settings.reads == (["text", "enabled"] if any_key else ["text"])
    callback.assert_not_called()
    settings.emit("enabled")
    assert callback.call_count == int(any_key)
    settings.emit("text")
    assert callback.call_args.args == ()
    assert callback.call_count == 1 + int(any_key)
    target.disconnect_all()
    target.disconnect_all()
    settings.history[0](settings, "text")
    assert callback.call_count == 1 + int(any_key)
    assert settings.disconnected == [1]


@pytest.mark.parametrize("any_key", [False, True])
@pytest.mark.parametrize("disconnect_fails", [False, True])
def test_partial_registration_is_cleaned_and_deactivated(monitor, any_key, disconnect_fails):
    settings = SignalSettings()
    settings.fail_read = "enabled" if any_key else "text"
    settings.fail_disconnect = disconnect_fails
    monitor.gio.Settings.new_full.side_effect = None
    monitor.gio.Settings.new_full.return_value = settings
    callback = Mock()
    target = monitor.monitor
    assert not (target.watch_any("test", callback) if any_key else
                target.watch("test", "text", callback))
    assert target._watchers == []
    assert settings.disconnected == [1]
    settings.history[0](settings, "text")
    callback.assert_not_called()


@pytest.mark.parametrize("phase", ["lookup", "list", "construct", "connect"])
def test_backend_failure_does_not_publish_registration(monitor, phase):
    settings = SignalSettings()
    if phase == "lookup":
        monitor.source.lookup.side_effect = RuntimeError("lookup failed")
    elif phase == "list":
        monitor.definition.list_keys.side_effect = RuntimeError("list failed")
    elif phase == "construct":
        monitor.gio.Settings.new_full.side_effect = RuntimeError("construction failed")
    else:
        settings.connect = Mock(side_effect=RuntimeError("connect failed"))
        monitor.gio.Settings.new_full.side_effect = None
        monitor.gio.Settings.new_full.return_value = settings
    assert not monitor.monitor.watch_any("test", Mock())
    assert monitor.monitor._watchers == []
    assert settings.disconnected == []


def test_disconnect_failure_does_not_keep_callbacks_alive(monitor):
    callback = Mock()
    assert monitor.monitor.watch("test", "text", callback)
    assert monitor.monitor.watch_any("test", callback)
    monitor.created[0].fail_disconnect = True
    monitor.monitor.disconnect_all()
    for settings in monitor.created:
        settings.history[0](settings, "text")
        assert settings.disconnected == [1]
    callback.assert_not_called()
    assert monitor.monitor._watchers == []


def test_callback_can_disconnect_then_register_again(monitor):
    new_callback = Mock()

    def replace():
        monitor.monitor.disconnect_all()
        assert monitor.monitor.watch("test", "enabled", new_callback)

    assert monitor.monitor.watch("test", "text", replace)
    first = monitor.created[0]
    first.emit("text")
    first.history[0](first, "text")
    assert len(monitor.created) == 2
    monitor.created[1].emit("enabled")
    new_callback.assert_called_once_with()


def test_independent_subscribers_receive_changes(monitor):
    first, second = Mock(), Mock()
    assert monitor.monitor.watch("test", "text", first)
    assert monitor.monitor.watch("test", "text", second)
    for settings in monitor.created:
        settings.emit("text")
    first.assert_called_once_with()
    second.assert_called_once_with()


def test_empty_fixed_schema_supports_watch_any(monitor):
    monitor.definition.list_keys.return_value = []
    assert monitor.monitor.watch_any("test", Mock())
    assert monitor.created[0].reads == []
