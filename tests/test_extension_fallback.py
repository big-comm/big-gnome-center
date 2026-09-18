# SPDX-License-Identifier: MIT
"""Reconcile Shell preferences without changing the desktop session."""

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from gi.repository import Gio

import extension_manager
from extension_manager import ExtMgr


@pytest.fixture
def backend(tmp_path, monkeypatch):
    memory = Gio.memory_settings_backend_new()

    def create(*args):
        return Gio.Settings.new_with_backend("org.gnome.shell", memory)

    settings = create()
    settings.set_strv("enabled-extensions", [])
    settings.set_strv("disabled-extensions", [])
    monkeypatch.setattr(extension_manager, "CONFIG_DIR", tmp_path, raising=False)
    monkeypatch.setattr(Gio.Settings, "new_full", create)
    monkeypatch.setattr(ExtMgr, "enabled_list", lambda: settings.get_strv("enabled-extensions"))
    # The previous implementation must fail without executing real CLI writes.
    monkeypatch.setattr(extension_manager, "run_cmd", Mock(return_value=(False, "CLI blocked")))
    return settings, create


@pytest.mark.parametrize("enable", [True, False])
@pytest.mark.parametrize("present", ["neither", "enabled", "disabled", "both"])
def test_fallback_reconciles_both_lists_without_losing_other_entries(backend, enable, present):
    settings, create = backend
    target = "target@example.org"
    enabled = ["keep'enabled@example.org", "slash\\name@example.org", "日本語@example.org"]
    disabled = ["keep'disabled@example.org", "other@example.org"]
    settings.set_strv(
        "enabled-extensions", enabled + ([target] if present in ("enabled", "both") else []),
    )
    settings.set_strv(
        "disabled-extensions", disabled + ([target] if present in ("disabled", "both") else []),
    )
    settings.set_boolean("disable-user-extensions", True)
    ok, message = ExtMgr._set_enabled_gsettings(target, enable)
    assert ok, message
    persisted = create()
    assert persisted.get_strv("enabled-extensions") == enabled + ([target] if enable else [])
    assert persisted.get_strv("disabled-extensions") == disabled + ([] if enable else [target])
    assert persisted.get_boolean("disable-user-extensions") is True
    extension_manager.run_cmd.assert_not_called()


@pytest.mark.parametrize("failure", ["locked", "setter", "apply", "verification"])
def test_failed_batch_never_reports_success(backend, monkeypatch, failure):
    settings, create = backend
    target = "target@example.org"
    settings.set_strv("enabled-extensions", [])
    settings.set_strv("disabled-extensions", [target])
    native = create()
    wrapped = Mock(wraps=native)
    if failure == "locked":
        wrapped.is_writable.side_effect = lambda key: key != "disabled-extensions"
    elif failure == "setter":
        wrapped.set_strv.side_effect = lambda key, value: (
            False if key == "disabled-extensions" else native.set_strv(key, value)
        )
    elif failure == "apply":
        wrapped.apply.side_effect = RuntimeError("backend failed")
    else:
        wrapped.apply.side_effect = lambda: None
    monkeypatch.setattr(Gio.Settings, "new_full", Mock(side_effect=[wrapped, create()]))
    ok, message = ExtMgr._set_enabled_gsettings(target, True)
    assert not ok
    assert message
    assert settings.get_strv("enabled-extensions") == []
    assert settings.get_strv("disabled-extensions") == [target]
    assert not native.get_has_unapplied()


def test_concurrent_fallback_updates_preserve_each_uuid(backend):
    settings, create = backend
    targets = [f"test-{index}@example.org" for index in range(24)]
    settings.set_strv("disabled-extensions", targets + ["keep@example.org"])
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert all(ok for ok, message in pool.map(
            lambda uuid: ExtMgr._set_enabled_gsettings(uuid, True), targets,
        ))
    assert set(create().get_strv("enabled-extensions")) == set(targets)
    assert create().get_strv("disabled-extensions") == ["keep@example.org"]


@pytest.mark.parametrize("uuid", [None, "", "../outside", "bad'uuid"])
def test_invalid_uuid_does_not_mutate_preferences(backend, uuid):
    settings, create = backend
    assert not ExtMgr._set_enabled_gsettings(uuid, True)[0]
    assert settings.get_strv("enabled-extensions") == []
    assert settings.get_strv("disabled-extensions") == []
    extension_manager.run_cmd.assert_not_called()


def test_unavailable_schema_does_not_construct_settings(backend, monkeypatch):
    monkeypatch.setattr(Gio.SettingsSchemaSource, "get_default", lambda: None)
    factory = Mock()
    monkeypatch.setattr(Gio.Settings, "new_full", factory)
    assert not ExtMgr._set_enabled_gsettings("target@example.org", True)[0]
    factory.assert_not_called()


@pytest.mark.parametrize("enable", [True, False])
def test_idempotent_fallback_preserves_order_without_rewriting_locked_keys(
    backend, monkeypatch, enable,
):
    settings, create = backend
    target = "target@example.org"
    selected = "enabled-extensions" if enable else "disabled-extensions"
    expected = ["first@example.org", target, "last@example.org"]
    settings.set_strv(selected, expected)
    wrapped = Mock(wraps=create())
    wrapped.is_writable.return_value = False
    monkeypatch.setattr(Gio.Settings, "new_full", lambda *args: wrapped)
    assert ExtMgr._set_enabled_gsettings(target, enable)[0]
    assert settings.get_strv(selected) == expected
    wrapped.set_strv.assert_not_called()
    wrapped.apply.assert_not_called()


@pytest.mark.parametrize("enable", [True, False])
def test_fallback_removes_duplicate_target_entries_only(backend, enable):
    settings, create = backend
    target = "target@example.org"
    for key in ("enabled-extensions", "disabled-extensions"):
        settings.set_strv(key, [target, "other@example.org", target, "other@example.org"])
    assert ExtMgr._set_enabled_gsettings(target, enable)[0]
    assert create().get_strv("enabled-extensions") == ["other@example.org"] * 2 + (
        [target] if enable else []
    )
    assert create().get_strv("disabled-extensions") == ["other@example.org"] * 2 + (
        [] if enable else [target]
    )


def test_failed_lock_never_changes_lists(backend, monkeypatch):
    settings, create = backend
    settings.set_strv("disabled-extensions", ["target@example.org"])
    monkeypatch.setattr("extension_manager.fcntl.flock", Mock(side_effect=OSError("lock failed")))
    ok, message = ExtMgr._set_enabled_gsettings("target@example.org", True)
    assert not ok and "lock failed" in message
    assert create().get_strv("enabled-extensions") == []
    assert create().get_strv("disabled-extensions") == ["target@example.org"]


def test_incomplete_schema_does_not_construct_settings(backend, monkeypatch):
    schema = Mock()
    schema.has_key.side_effect = lambda key: key == "enabled-extensions"
    source = Mock()
    source.lookup.return_value = schema
    monkeypatch.setattr(Gio.SettingsSchemaSource, "get_default", lambda: source)
    factory = Mock()
    monkeypatch.setattr(Gio.Settings, "new_full", factory)
    assert not ExtMgr._set_enabled_gsettings("target@example.org", True)[0]
    factory.assert_not_called()
