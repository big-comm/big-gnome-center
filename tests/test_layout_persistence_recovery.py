# SPDX-License-Identifier: MIT
"""Failed layout writes recover this operation's files, never a shared .bak."""

import hashlib
from pathlib import Path
from unittest.mock import Mock

import pytest

import layout_applier as module
from helper_client import HELPER_UUID, LEGACY_HELPER_UUID

DATA = (
    "[org/gnome/shell]\nenabled-extensions=@as []\n\n"
    "[org/example/layout]\nname='target'\n"
    "description='Target layout for isolated persistence recovery tests.'\n"
)
OLD = DATA.replace("target", "previous")


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "open_store", Mock())
    monkeypatch.setattr(module.LayoutApplier, "_refresh_sync_monitor", Mock())
    for name, filename in (
        ("SETTINGS_GNOME", "settings.gnome"),
        ("_LAYOUT_HASH_FILE", "settings.sha256"),
        ("_LAYOUT_MUTATION_LOCK_PATH", "mutation.lock"),
        ("_SYNC_LOCK_PATH", "sync.lock"),
    ):
        monkeypatch.setattr(module, name, tmp_path / filename)
    module.SETTINGS_GNOME.write_text(OLD)
    module._LAYOUT_HASH_FILE.write_text("previous marker\n")
    mocks = {}
    for owner, name, result in (
        (module.HelperClient, "ensure_available", (True, "")),
        (module.HelperClient, "active_uuid", HELPER_UUID),
        (module.HelperClient, "discover_installed_components", (True, "")),
        (module.HelperClient, "installed_extension_uuids", set()),
        (module.HelperClient, "helper_version", 7),
        (module.HelperClient, "ping_info", {"uuid": HELPER_UUID}),
        (module.HelperClient, "begin_switch", (False, "begin failed")),
        (module.HelperClient, "abort_switch", True),
        (module.HelperClient, "complete_switch", (True, "completed")),
        (module.HelperClient, "apply_layout", (False, "incremental failed")),
        (module.LayoutApplier, "_validate_structural_extensions", (True, "")),
        (module.LayoutApplier, "_qt_theme_watcher", None),
        (module.LayoutApplier, "_enabled_extensions", []),
        (module.LayoutApplier, "_managed_extension_subdirs", []),
        (module.ShellReloader, "list_extensions_state", {}),
        (module, "run_cmd", (True, "")),
    ):
        mocks[name] = Mock(return_value=result)
        monkeypatch.setattr(owner, name, mocks[name])
    for name in ("_preserve_layout_independent_settings", "_apply_user_component_overrides"):
        monkeypatch.setattr(module.LayoutApplier, name, lambda data, **kwargs: data)
    return mocks


def content(path):
    return path.read_bytes() if path.exists() else None


@pytest.mark.parametrize("previous", [None, "", "short\n", OLD, OLD.replace("\n", "\r\n")])
@pytest.mark.parametrize("marker", [None, "", "custom marker\n"])
def test_failure_restores_exact_previous_files(session, previous, marker):
    for path, value in ((module.SETTINGS_GNOME, previous), (module._LAYOUT_HASH_FILE, marker)):
        path.unlink()
        if value is not None:
            path.write_bytes(value.encode())
    ok, message = module.LayoutApplier.load_dconf_safely(DATA)
    assert not ok
    assert "begin failed" in message
    assert content(module.SETTINGS_GNOME) == (previous.encode() if previous is not None else None)
    assert content(module._LAYOUT_HASH_FILE) == (marker.encode() if marker is not None else None)
    assert not module._SYNC_LOCK_PATH.exists()


@pytest.mark.parametrize("backup", ["stale", "directory"])
def test_recovery_does_not_depend_on_backup_update(session, monkeypatch, backup):
    path = module.SETTINGS_GNOME.with_suffix(".gnome.bak")
    stale = OLD.replace("previous", "obsolete")
    if backup == "directory":
        path.mkdir()
    else:
        path.write_text(stale)
        write = Path.write_bytes

        def denied(self, data):
            if self == path:
                raise PermissionError("backup is read-only")
            return write(self, data)
        monkeypatch.setattr(Path, "write_bytes", denied)
    ok, message = module.LayoutApplier.load_dconf_safely(DATA)
    assert not ok
    assert "begin failed" in message
    assert module.SETTINGS_GNOME.read_text() == OLD
    assert module._LAYOUT_HASH_FILE.read_text() == "previous marker\n"
    assert path.is_dir() if backup == "directory" else path.read_text() == stale


def test_recovery_does_not_rotate_backup_again(session):
    assert not module.LayoutApplier.load_dconf_safely(DATA)[0]
    assert module.SETTINGS_GNOME.with_suffix(".gnome.bak").read_text() == OLD


@pytest.mark.parametrize("route", ["busy", "dump", "begin", "complete", "incremental", "external"])
def test_live_failure_routes_restore_files(session, route):
    if route == "busy":
        session["ping_info"].return_value = {"busy": True}
    elif route == "dump":
        session["run_cmd"].return_value = (False, "dump failed")
    elif route == "complete":
        session["begin_switch"].return_value = (True, "")
        session["complete_switch"].return_value = (False, "complete failed")
    elif route == "incremental":
        session["helper_version"].return_value = 6
    elif route == "external":
        session["helper_version"].return_value = 0
        session["run_cmd"].side_effect = lambda argv, **kw: (
            (False, "load failed") if argv[:2] == ["dconf", "load"] else (True, "")
        )
    assert not module.LayoutApplier.load_dconf_safely(DATA)[0]
    assert module.SETTINGS_GNOME.read_text() == OLD
    assert module._LAYOUT_HASH_FILE.read_text() == "previous marker\n"


def test_exception_recovers_before_releasing_watcher_protection(session):
    session["begin_switch"].side_effect = ValueError("helper exception")

    def watcher(action):
        if action == "start":
            assert module.SETTINGS_GNOME.read_text() == OLD
            assert module._SYNC_LOCK_PATH.exists()
    session["_qt_theme_watcher"].side_effect = watcher
    with pytest.raises(ValueError, match="helper exception"):
        module.LayoutApplier.load_dconf_safely(DATA)
    assert not module._SYNC_LOCK_PATH.exists()


@pytest.mark.parametrize("path_name", ["SETTINGS_GNOME", "_LAYOUT_HASH_FILE"])
def test_capture_failure_stops_before_persistence_and_teardown(session, monkeypatch, path_name):
    path = getattr(module, path_name)
    read = Path.read_bytes

    def denied(self):
        if self == path:
            raise PermissionError("cannot capture file")
        return read(self)
    monkeypatch.setattr(Path, "read_bytes", denied)
    ok, message = module.LayoutApplier.load_dconf_safely(DATA)
    assert not ok
    assert "cannot capture file" in message
    session["begin_switch"].assert_not_called()
    assert module.SETTINGS_GNOME.read_text() == OLD


@pytest.mark.parametrize("path_name", ["SETTINGS_GNOME", "_LAYOUT_HASH_FILE"])
def test_recovery_failure_preserves_original_error_and_reports_failed_restore(
    session, monkeypatch, path_name
):
    atomic = module.atomic_write_text
    path = getattr(module, path_name)
    previous = path.read_text()

    def fail(dest, data, **kwargs):
        if dest == path and data == previous:
            raise OSError("recovery write failed")
        return atomic(dest, data, **kwargs)
    monkeypatch.setattr(module, "atomic_write_text", fail)
    ok, message = module.LayoutApplier.load_dconf_safely(DATA)
    assert not ok
    assert "begin failed" in message
    assert "recovery write failed" in message
    assert not module._SYNC_LOCK_PATH.exists()
    if path_name == "SETTINGS_GNOME":
        # Keep the marker associated with the still-published target.
        assert hashlib.sha256(module.SETTINGS_GNOME.read_bytes()).hexdigest() in (
            module._LAYOUT_HASH_FILE.read_text()
        )


@pytest.mark.parametrize("success", [False, True])
def test_no_persistence_never_reads_or_recovers_files(session, monkeypatch, success):
    session["begin_switch"].return_value = (success, "begin failed")
    read = Path.read_bytes

    def deny_settings(self):
        assert self not in (module.SETTINGS_GNOME, module._LAYOUT_HASH_FILE)
        return read(self)
    monkeypatch.setattr(Path, "read_bytes", deny_settings)
    result = module.LayoutApplier.load_dconf_safely(DATA, persist=False)
    assert result[0] == success
    assert module.SETTINGS_GNOME.read_text() == OLD
    assert module._LAYOUT_HASH_FILE.read_text() == "previous marker\n"


def test_success_publishes_target_and_matching_hash(session):
    session["begin_switch"].return_value = (True, "")
    assert module.LayoutApplier.load_dconf_safely(DATA)[0]
    assert "name='target'" in module.SETTINGS_GNOME.read_text()
    assert hashlib.sha256(module.SETTINGS_GNOME.read_bytes()).hexdigest() in (
        module._LAYOUT_HASH_FILE.read_text()
    )


def test_persistence_failure_after_replace_recovers_previous_files(session, monkeypatch):
    atomic = module.atomic_write_text

    def fail(dest, data, **kwargs):
        atomic(dest, data, **kwargs)
        if dest == module.SETTINGS_GNOME and "name='target'" in data:
            raise OSError("failure after replace")
    monkeypatch.setattr(module, "atomic_write_text", fail)
    ok, message = module.LayoutApplier.load_dconf_safely(DATA)
    assert not ok
    assert "failure after replace" in message
    session["begin_switch"].assert_not_called()
    assert module.SETTINGS_GNOME.read_text() == OLD
    assert module._LAYOUT_HASH_FILE.read_text() == "previous marker\n"


@pytest.mark.parametrize("failure", [None, "capture", "write", "exception"])
def test_staged_migration_keeps_success_and_recovers_failed_writes(session, monkeypatch, failure):
    session["active_uuid"].return_value = LEGACY_HELPER_UUID
    if failure == "capture":
        monkeypatch.setattr(
            module.LayoutApplier, "_capture_persisted_settings",
            Mock(side_effect=OSError("capture failed")),
        )
    elif failure in {"write", "exception"}:
        persist = module.LayoutApplier._persist_to_settings_file

        def fail(data):
            assert persist(data)[0]
            if failure == "exception":
                raise ValueError("persistence exception")
            return False, "write failed"
        monkeypatch.setattr(module.LayoutApplier, "_persist_to_settings_file", fail)
    if failure == "exception":
        with pytest.raises(ValueError, match="persistence exception"):
            module.LayoutApplier.load_dconf_safely(DATA)
    else:
        ok, message = module.LayoutApplier.load_dconf_safely(DATA)
        assert ok == (failure is None)
    session["begin_switch"].assert_not_called()
    assert module.LayoutApplier.last_apply_staged == (failure is None)
    assert not module._SYNC_LOCK_PATH.exists()
    if failure:
        assert module.SETTINGS_GNOME.read_text() == OLD
        assert module._LAYOUT_HASH_FILE.read_text() == "previous marker\n"
    else:
        assert "name='target'" in module.SETTINGS_GNOME.read_text()


def test_recovery_unlink_failure_is_reported(session, monkeypatch):
    module.SETTINGS_GNOME.unlink()
    unlink = Path.unlink

    def fail(self, **kwargs):
        if self == module.SETTINGS_GNOME:
            raise PermissionError("cannot remove failed target")
        return unlink(self, **kwargs)
    monkeypatch.setattr(Path, "unlink", fail)
    ok, message = module.LayoutApplier.load_dconf_safely(DATA)
    assert not ok
    assert "begin failed" in message
    assert "cannot remove failed target" in message
    assert not module._SYNC_LOCK_PATH.exists()


def test_invalid_utf8_capture_preserves_bytes_and_stops_before_write(session):
    module.SETTINGS_GNOME.write_bytes(b"\xff\xfe")
    ok, message = module.LayoutApplier.load_dconf_safely(DATA)
    assert not ok
    assert "capture" in message
    assert module.SETTINGS_GNOME.read_bytes() == b"\xff\xfe"
    session["begin_switch"].assert_not_called()


def test_exception_and_recovery_failure_are_both_reported(session, monkeypatch):
    original = ValueError("original failure")
    session["begin_switch"].side_effect = original
    atomic = module.atomic_write_text

    def fail(dest, data, **kwargs):
        if dest == module.SETTINGS_GNOME and data == OLD:
            raise OSError("recovery failure")
        atomic(dest, data, **kwargs)
    monkeypatch.setattr(module, "atomic_write_text", fail)
    with pytest.raises(RuntimeError, match="original failure.*recovery failure") as raised:
        module.LayoutApplier.load_dconf_safely(DATA)
    assert raised.value.__cause__ is original
    assert not module._SYNC_LOCK_PATH.exists()


def test_retry_captures_new_operation_state(session):
    assert not module.LayoutApplier.load_dconf_safely(DATA)[0]
    session["begin_switch"].return_value = True, ""
    assert module.LayoutApplier.load_dconf_safely(DATA)[0]
    target_bytes = module.SETTINGS_GNOME.read_bytes()
    marker_bytes = module._LAYOUT_HASH_FILE.read_bytes()
    session["begin_switch"].return_value = False, "later failed"
    assert not module.LayoutApplier.load_dconf_safely(DATA.replace("target", "another"))[0]
    assert module.SETTINGS_GNOME.read_bytes() == target_bytes
    assert module._LAYOUT_HASH_FILE.read_bytes() == marker_bytes
