# SPDX-License-Identifier: MIT
"""Launch completion, fallback ordering and main-loop responsiveness."""

import json
import sys
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from gi.repository import GLib

import app_launcher as launcher
import extension_manager as manager


def drain_until(predicate, timeout=10):
    context = GLib.MainContext.default()
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        time.sleep(0.005)
    assert predicate(), "asynchronous operation did not finish"


@pytest.mark.parametrize("status", [0, 7])
def test_native_command_completion_once(status):
    errors, successes = [], []
    launcher.launch_command(
        [sys.executable, "-c", f"raise SystemExit({status})"], errors.append,
        on_success=lambda: successes.append(True),
    )
    drain_until(lambda: errors or successes)
    assert len(errors) == (status != 0)
    assert len(successes) == (status == 0)


def test_missing_command_reports_error_once(tmp_path):
    errors, successes = [], []
    launcher.launch_command([str(tmp_path / "missing")], errors.append,
                            on_success=lambda: successes.append(True))
    assert len(errors) == 1
    assert not successes


def test_native_argv_is_literal(tmp_path):
    destination = tmp_path / "arguments.json"
    marker = tmp_path / "must-not-exist"
    arguments = ["a b", f"$(touch {marker})", "quotes'\"", "https://example.org/?a=1&b=2"]
    errors, done = [], []
    launcher.launch_command([
        sys.executable, "-c",
        "import json,sys; from pathlib import Path; "
        "Path(sys.argv[1]).write_text(json.dumps(sys.argv[2:]))",
        str(destination), *arguments,
    ], errors.append, on_success=lambda: done.append(True))
    drain_until(lambda: done or errors)
    assert not errors
    assert json.loads(destination.read_text()) == arguments
    assert not marker.exists()


def test_running_application_survives_five_seconds_and_keeps_loop_responsive():
    errors, done, ticks = [], [], []
    timer = GLib.timeout_add(20, lambda: ticks.append(True) or GLib.SOURCE_CONTINUE)
    start = time.monotonic()
    try:
        launcher.launch_command(
            [sys.executable, "-c", "import time; time.sleep(6)"], errors.append,
            on_success=lambda: done.append(True),
        )
        assert time.monotonic() - start < 1
        drain_until(lambda: done or errors)
    finally:
        GLib.source_remove(timer)
    assert not errors
    assert done == [True]
    assert time.monotonic() - start >= 5.8
    assert len(ticks) > 50


def test_only_bounded_preparation_times_out_once():
    errors, successes = [], []
    launcher.launch_command(
        [sys.executable, "-c", "import time; time.sleep(4)"], errors.append,
        on_success=lambda: successes.append(True), timeout=1,
    )
    drain_until(lambda: errors)
    # Reap delivery must not report a second error after force_exit().
    context = GLib.MainContext.default()
    deadline = time.monotonic() + 0.2
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        time.sleep(0.005)
    assert len(errors) == 1
    assert "timed out" in errors[0]
    assert not successes


def test_success_cancels_preparation_timer(monkeypatch):
    child = Mock()
    monkeypatch.setattr(launcher.Gio.Subprocess, "new", Mock(return_value=child))
    add = Mock(return_value=123)
    remove = Mock()
    monkeypatch.setattr(launcher.GLib, "timeout_add_seconds", add)
    monkeypatch.setattr(launcher.GLib, "source_remove", remove)
    success = Mock()
    launcher.launch_command(["compiler"], on_success=success, timeout=20)
    callback = child.wait_check_async.call_args.args[1]
    callback(child, object())
    remove.assert_called_once_with(123)
    success.assert_called_once_with()
    child.force_exit.assert_not_called()


@pytest.mark.parametrize("failure", ["none", "start", "finish"])
def test_uri_launch_reports_async_failures(monkeypatch, failure):
    error = GLib.Error("activation failed")
    start = Mock(side_effect=error if failure == "start" else None)
    finish = Mock(side_effect=error if failure == "finish" else None)
    monkeypatch.setattr(launcher.Gio.AppInfo, "launch_default_for_uri_async", start)
    monkeypatch.setattr(launcher.Gio.AppInfo, "launch_default_for_uri_finish", finish)
    errors = []
    uri = "https://example.org/?a=one%20two&b=three"
    launcher.launch_uri(uri, errors.append)
    assert start.call_args.args[0] == uri
    if failure != "start":
        result = object()
        start.call_args.args[3](None, result)
        finish.assert_called_once_with(result)
    assert len(errors) == (failure != "none")


@pytest.mark.parametrize("available", [[], ["gnome-extensions-app"],
                                       ["gnome-shell-extension-prefs"],
                                       ["gnome-extensions-app", "gnome-shell-extension-prefs"]])
def test_extension_manager_fallback_requires_failure(monkeypatch, available):
    monkeypatch.setattr(launcher.shutil, "which", lambda cmd: cmd if cmd in available else None)
    command, uri, error = Mock(), Mock(), Mock()
    monkeypatch.setattr(launcher, "launch_command", command)
    monkeypatch.setattr(launcher, "launch_uri", uri)
    launcher.launch_extensions_app(error)
    for index, name in enumerate(available):
        assert command.call_count == index + 1
        assert command.call_args.args[0] == [name]
        uri.assert_not_called()
        # Until the active child reports failure, no fallback is launched.
        command.call_args.args[1]("launch failed")
    uri.assert_called_once_with("https://extensions.gnome.org", error)
    error.assert_not_called()


@pytest.fixture
def preferences(tmp_path, monkeypatch):
    monkeypatch.setattr(manager, "EXT_USER_DIR", tmp_path)
    monkeypatch.setattr(manager.shutil, "which", lambda command: command)
    launch = Mock()
    monkeypatch.setattr(manager, "launch_command", launch)
    return tmp_path, launch


def test_preferences_fallback_is_async(preferences):
    root, launch = preferences
    errors = []
    manager.ExtMgr.open_prefs("test@example.org", errors.append)
    assert launch.call_count == 1
    assert launch.call_args.args[0] == ["gnome-extensions", "prefs", "test@example.org"]
    assert "timeout" not in launch.call_args.kwargs
    launch.call_args.args[1]("CLI failed")
    assert launch.call_count == 2
    argv = launch.call_args.args[0]
    assert argv[0] == "gdbus"
    assert argv[-3:] == ["test@example.org", "", "{}"]
    launch.call_args.args[1]("D-Bus failed")
    assert errors == ["D-Bus failed"]


def test_preferences_without_cli_uses_dbus(preferences, monkeypatch):
    root, launch = preferences
    monkeypatch.setattr(manager.shutil, "which", lambda command: None)
    manager.ExtMgr.open_prefs("test@example.org")
    assert launch.call_count == 1
    assert launch.call_args.args[0][0] == "gdbus"


@pytest.mark.parametrize("success", [True, False])
def test_preferences_wait_for_schema_preparation(preferences, success):
    root, launch = preferences
    schemas = root / "test@example.org" / "schemas"
    schemas.mkdir(parents=True)
    (schemas / "test.gschema.xml").touch()
    errors = []
    manager.ExtMgr.open_prefs("test@example.org", errors.append)
    assert launch.call_count == 1
    assert launch.call_args.args[0] == ["glib-compile-schemas", "--strict", str(schemas)]
    assert launch.call_args.kwargs["timeout"] == 20
    if success:
        launch.call_args.kwargs["on_success"]()
        assert launch.call_count == 2
        assert launch.call_args.args[0][0] == "gnome-extensions"
    else:
        launch.call_args.args[1]("invalid schema")
        assert launch.call_count == 1
        assert errors == ["invalid schema"]


@pytest.mark.parametrize("uuid", ["", "../escape", "-option", None])
def test_invalid_preferences_uuid_never_launches(preferences, uuid):
    root, launch = preferences
    errors = []
    manager.ExtMgr.open_prefs(uuid, errors.append)
    launch.assert_not_called()
    assert len(errors) == 1


@pytest.mark.parametrize("valid", [True, False])
def test_native_schema_preparation_gates_preferences(tmp_path, monkeypatch, valid):
    monkeypatch.setattr(manager, "EXT_USER_DIR", tmp_path)
    monkeypatch.setattr(manager.shutil, "which", lambda command: command)
    schemas = tmp_path / "test@example.org" / "schemas"
    schemas.mkdir(parents=True)
    xml = ('<schemalist><schema id="org.bgc.test" path="/org/bgc/test/">'
           '<key name="enabled" type="b"><default>false</default></key>'
           '</schema></schemalist>')
    (schemas / "test.gschema.xml").write_text(xml if valid else "<invalid>")
    opened, errors = [], []

    def launch(argv, on_error=None, **kwargs):
        if argv[0] == "gnome-extensions":
            assert (schemas / "gschemas.compiled").is_file()
            opened.append(argv)
        else:
            launcher.launch_command(argv, on_error, **kwargs)

    monkeypatch.setattr(manager, "launch_command", launch)
    manager.ExtMgr.open_prefs("test@example.org", errors.append)
    drain_until(lambda: opened or errors)
    assert bool(opened) is valid
    assert bool(errors) is not valid


def test_extensions_page_uses_nonblocking_launcher(monkeypatch):
    from ui.page_extensions import ExtensionsPage

    launch = Mock()
    monkeypatch.setattr("ui.page_extensions.launch_extensions_app", launch)
    page = SimpleNamespace(_launch_error=Mock())
    ExtensionsPage._open_gnome_extensions(page, None)
    launch.assert_called_once_with(page._launch_error)


@pytest.mark.parametrize("module,cls", [("ui.page_extensions", "ExtensionsPage"),
                                      ("ui.page_effects", "EffectsPage"),
                                      ("ui.ext_detail_view", "ExtDetailView")])
def test_pages_surface_launch_errors(module, cls):
    import importlib

    page_type = getattr(importlib.import_module(module), cls)
    page = SimpleNamespace(_toast=Mock())
    page_type._launch_error(page, "backend refused")
    assert "backend refused" in page._toast.call_args.args[0]
