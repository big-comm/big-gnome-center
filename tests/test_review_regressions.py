# SPDX-License-Identifier: MIT
"""Persistence and incomplete-check regressions."""

import concurrent.futures
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

import constants
import settings_store
from extension_update_monitor import ExtensionUpdateMonitor
from update_checker import UpdateCheckError, check_all


@pytest.mark.parametrize("value", ["", "relative", "/tmp/custom-config"])
def test_xdg_home_requires_absolute_path(monkeypatch, value):
    monkeypatch.setenv("XDG_CONFIG_HOME", value)
    expected = Path(value) if value.startswith("/") else Path.home() / ".config"
    assert constants._xdg_home("XDG_CONFIG_HOME", ".config") == expected


def test_xdg_migration_preserves_existing_and_imports_previous_path(tmp_path, monkeypatch):
    home = tmp_path / "home"
    old = home / ".config/big-gnome-center"
    new = tmp_path / "xdg/big-gnome-center"
    old.mkdir(parents=True)
    (old / "settings.json").write_text('{"active_layout":"Classic"}')
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(constants, "CONFIG_DIR", new)
    monkeypatch.setattr(constants, "CACHE_DIR", tmp_path / "cache/big-gnome-center")
    monkeypatch.setattr(constants, "_migrate_settings_app_folder", lambda: None)
    constants.migrate_user_data()
    assert (new / "settings.json").read_bytes() == (old / "settings.json").read_bytes()
    (new / "settings.json").write_text('{"active_layout":"Minimal"}')
    constants.migrate_user_data()
    assert "Minimal" in (new / "settings.json").read_text()


def test_incomplete_check_preserves_successful_results():
    detail = SimpleNamespace(pk=12)
    with (
        patch("update_checker.ExtMgr.list_installed", return_value=[
            {"uuid": "good", "user": True}, {"uuid": "bad", "user": True},
        ]),
        patch("update_checker.ExtMgr.installed_version", return_value=1),
        patch("update_checker._shell_version_str", return_value="50"),
        patch("update_checker.ego_client.info", side_effect=[detail, OSError("offline")]),
        patch("update_checker.ego_client.version_from_info", return_value=2),
    ):
        with pytest.raises(UpdateCheckError) as error:
            check_all()
    assert set(error.value.updates) == {"good"}


def test_failed_background_check_does_not_mark_success():
    settings = Mock()
    monitor = ExtensionUpdateMonitor(settings_factory=lambda: settings, notifier=Mock())
    future = concurrent.futures.Future()
    future.set_exception(UpdateCheckError(["offline"], {}))
    try:
        monitor._checking = True
        assert monitor._finish_check(future) is False
        assert not monitor._checking
        settings.set.assert_not_called()
        settings.delete.assert_not_called()
    finally:
        monitor._executor.shutdown(wait=True)


def test_notification_save_failure_does_not_preview_or_report_success(tmp_path, monkeypatch):
    from ui.page_desktop import DesktopPage

    monkeypatch.setattr(settings_store, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", tmp_path / "settings.json")
    prefs = settings_store.Settings()
    prefs.set("notification_positions", {"Classic": "top-center"})
    page = SimpleNamespace(
        _prefs=prefs, _active_layout="Classic", _toast=Mock(), refresh=Mock(),
        _send_notification_preview=Mock(),
    )
    page._save_preference = lambda key, value: DesktopPage._save_preference(page, key, value)
    with (
        patch("settings_store.atomic_write_text", side_effect=PermissionError("denied")),
        patch("ui.page_desktop.GLib.timeout_add") as timer,
    ):
        DesktopPage._finish_notification_position_change(page, True, "", "bottom-right", "Bottom right")
    timer.assert_not_called()
    assert "denied" in page._toast.call_args.args[0]
    assert prefs.get("notification_positions") == {"Classic": "top-center"}
    page.refresh.assert_called_once()


def test_failed_manual_check_does_not_claim_up_to_date():
    from ui.window import MainWindow

    page = SimpleNamespace(
        _update_check_running=True, _pending_updates={"known": object()},
        _pages={}, _toast=Mock(),
    )
    MainWindow._on_update_check_done(page, {}, True, True)
    assert not page._update_check_running
    assert "known" in page._pending_updates
    assert page._toast.call_args.args[0] == f"{constants.tr('Check for updates')}: {constants.tr('Operation failed')}"


def test_auto_update_toggle_does_not_change_state_on_save_failure():
    from ui.window import MainWindow

    prefs = Mock(last_error="denied")
    prefs.set.return_value = False
    page = SimpleNamespace(_prefs=prefs, _toast=Mock())
    action = Mock()
    action.get_state().get_boolean.return_value = False
    MainWindow._on_toggle_auto_update(page, action, None)
    action.set_state.assert_not_called()
    assert "denied" in page._toast.call_args.args[0]


@pytest.mark.parametrize("error", [UpdateCheckError(["offline"], {}), OSError("offline")])
def test_window_worker_does_not_mark_failed_check(error):
    from ui.window import MainWindow

    page = SimpleNamespace(
        _update_check_running=False, _prefs=Mock(), _on_update_check_done=Mock(),
        _pool=SimpleNamespace(submit=lambda task: task()),
    )
    with (
        patch("ui.window.update_checker.check_all", side_effect=error),
        patch("ui.window.update_checker.mark_checked") as mark,
        patch("ui.window.GLib.idle_add") as idle,
    ):
        MainWindow._run_update_check(page, True, True)
    mark.assert_not_called()
    idle.assert_called_once_with(page._on_update_check_done, {}, True, True)


def test_audit_uses_same_settings_path_and_rejects_non_object_json(tmp_path, monkeypatch):
    from runtime_audit import _application_active_layout

    path = tmp_path / "xdg/big-gnome-center/settings.json"
    path.parent.mkdir(parents=True)
    monkeypatch.setattr(constants, "SETTINGS_FILE", path)
    path.write_text('{"active_layout":"Classic"}')
    assert _application_active_layout() == "Classic"
    path.write_text('[]')
    assert _application_active_layout() == ""
