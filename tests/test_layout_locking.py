# SPDX-License-Identifier: MIT
"""Reject overlapping layout writes and fail before unprotected mutations."""

import fcntl
import multiprocessing
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock

import pytest

import layout_applier as module
from helper_client import HELPER_UUID, LEGACY_HELPER_UUID

DATA = "[org/gnome/shell]\nenabled-extensions=[]\n"


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "open_store", Mock())
    monkeypatch.setattr(module.LayoutApplier, "_refresh_sync_monitor", Mock())
    monkeypatch.setattr(module, "SETTINGS_GNOME", tmp_path / "settings.gnome")
    monkeypatch.setattr(module, "_LAYOUT_HASH_FILE", tmp_path / "settings.sha256")
    monkeypatch.setattr(
        module, "_LAYOUT_MUTATION_LOCK_PATH", tmp_path / "mutation.lock", raising=False
    )
    monkeypatch.setattr(module, "_SYNC_LOCK_PATH", tmp_path / "runtime/sync.lock")
    mocks = {}
    for owner, name, result in (
        (module.HelperClient, "ensure_available", (True, "")),
        (module.HelperClient, "active_uuid", HELPER_UUID),
        (module.HelperClient, "discover_installed_components", (True, "")),
        (module.HelperClient, "installed_extension_uuids", set()),
        (module.HelperClient, "helper_version", 7),
        (module.LayoutApplier, "_validate_structural_extensions", (True, "")),
        (module.LayoutApplier, "_persist_to_settings_file", (True, "")),
        (module.LayoutApplier, "_qt_theme_watcher", None),
        (module.LayoutApplier, "_renew_settings_freshness", None),
        (module.LayoutApplier, "_apply_via_helper_v7", (True, "applied")),
        (module, "run_cmd", (True, "")),
    ):
        mocks[name] = Mock(return_value=result)
        monkeypatch.setattr(owner, name, mocks[name])
    for name in ("_preserve_layout_independent_settings", "_apply_user_component_overrides"):
        monkeypatch.setattr(module.LayoutApplier, name, lambda data, **kwargs: data)
    return mocks


@pytest.mark.parametrize("route,persist", [
    (route, persist) for route in ("fallback", "incremental", "cleanroom", "staged")
    for persist in (False, True) if route != "staged" or persist
])
def test_overlapping_apply_is_rejected_before_preflight(isolated, monkeypatch, route, persist):
    entered, release = threading.Event(), threading.Event()

    def apply(*args, **kwargs):
        module.LayoutApplier.last_apply_cleanroom = True
        entered.set()
        assert release.wait(5)
        return True, "first"

    if route == "staged":
        isolated["active_uuid"].return_value = LEGACY_HELPER_UUID
        isolated["_persist_to_settings_file"].side_effect = apply
    elif route == "fallback":
        isolated["helper_version"].return_value = 0
        monkeypatch.setattr(module.LayoutApplier, "_reset_orphan_keys", apply)
        monkeypatch.setattr(module.LayoutApplier, "_enabled_extensions", lambda: [])
    elif route == "incremental":
        isolated["helper_version"].return_value = 6
        monkeypatch.setattr(module.LayoutApplier, "_apply_via_helper", apply)
    else:
        isolated["_apply_via_helper_v7"].side_effect = apply
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(module.LayoutApplier.load_dconf_safely, DATA, persist=persist)
        try:
            assert entered.wait(5)
            marker = module._SYNC_LOCK_PATH.read_text()
            result = module.LayoutApplier.load_dconf_safely(DATA, persist=persist)
            assert result[0] is False
            assert "in progress" in result[1]
            assert module._SYNC_LOCK_PATH.read_text() == marker
            assert module.LayoutApplier.last_apply_cleanroom is True
            isolated["ensure_available"].assert_called_once()
        finally:
            release.set()
        assert first.result(timeout=5)[0]
    assert not module._SYNC_LOCK_PATH.exists()
    assert isolated["_persist_to_settings_file"].call_count == int(persist)


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("persist", [False, True])
def test_marker_failure_prevents_persistence_and_switch(isolated, monkeypatch, legacy, persist):
    # A file where the runtime directory should be gives a real mkdir failure.
    module._SYNC_LOCK_PATH.parent.write_text("not a directory")
    isolated["active_uuid"].return_value = LEGACY_HELPER_UUID if legacy else HELPER_UUID
    ok, message = module.LayoutApplier.load_dconf_safely(DATA, persist=persist)
    assert not ok
    assert message
    isolated["_persist_to_settings_file"].assert_not_called()
    isolated["_apply_via_helper_v7"].assert_not_called()
    isolated["_qt_theme_watcher"].assert_not_called()
    assert module._SYNC_LOCK_PATH.parent.read_text() == "not a directory"


def test_failed_marker_publication_preserves_previous_contents(isolated, monkeypatch):
    module._SYNC_LOCK_PATH.parent.mkdir()
    module._SYNC_LOCK_PATH.write_text("previous owner\n")
    monkeypatch.setattr("utils.os.replace", Mock(side_effect=OSError("disk failure")))
    ok, message = module.LayoutApplier.load_dconf_safely(DATA)
    assert not ok
    assert "disk failure" in message
    assert module._SYNC_LOCK_PATH.read_text() == "previous owner\n"
    isolated["_persist_to_settings_file"].assert_not_called()
    assert list(module._SYNC_LOCK_PATH.parent.iterdir()) == [module._SYNC_LOCK_PATH]


def test_mutation_lock_open_failure_prevents_preflight(isolated, monkeypatch, tmp_path):
    blocked = tmp_path / "blocked"
    blocked.write_text("file")
    monkeypatch.setattr(module, "_LAYOUT_MUTATION_LOCK_PATH", blocked / "operation.lock")
    ok, message = module.LayoutApplier.load_dconf_safely(DATA)
    assert not ok
    assert message
    isolated["ensure_available"].assert_not_called()
    assert not module._SYNC_LOCK_PATH.exists()


@pytest.mark.parametrize("failure", ["refused", "exception", "restart", "freshness"])
def test_failure_releases_locks_for_next_attempt(isolated, failure):
    if failure == "refused":
        isolated["_apply_via_helper_v7"].return_value = (False, "rejected")
        assert not module.LayoutApplier.load_dconf_safely(DATA)[0]
    else:
        target = {
            "exception": "_apply_via_helper_v7",
            "restart": "_qt_theme_watcher",
            "freshness": "_renew_settings_freshness",
        }[failure]
        if failure == "restart":
            isolated[target].side_effect = [None, RuntimeError("restart failed")]
        else:
            isolated[target].side_effect = RuntimeError("injected failure")
        with pytest.raises(RuntimeError):
            module.LayoutApplier.load_dconf_safely(DATA)
        isolated[target].side_effect = None
    assert not module._SYNC_LOCK_PATH.exists()
    inode = module._LAYOUT_MUTATION_LOCK_PATH.stat().st_ino
    isolated["_apply_via_helper_v7"].return_value = (True, "retry")
    assert module.LayoutApplier.load_dconf_safely(DATA) == (True, "retry")
    assert module._LAYOUT_MUTATION_LOCK_PATH.stat().st_ino == inode


def _hold_lock(path, connection):
    with Path(path).open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        connection.send("locked")
        connection.recv()


def test_process_contention_and_crashed_owner_release(isolated):
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=_hold_lock, args=(module._LAYOUT_MUTATION_LOCK_PATH, child))
    process.start()
    child.close()
    try:
        assert parent.poll(10)
        assert parent.recv() == "locked"
        ok, message = module.LayoutApplier.load_dconf_safely(DATA)
        assert not ok
        assert "in progress" in message
        isolated["ensure_available"].assert_not_called()
    finally:
        process.kill()
        process.join(timeout=5)
        parent.close()
    assert not process.is_alive()
    assert module.LayoutApplier.load_dconf_safely(DATA)[0]


def test_successful_marker_contains_pid_during_switch(isolated):
    def apply(*args, **kwargs):
        assert module._SYNC_LOCK_PATH.read_text() == f"{os.getpid()}\n"
        return True, ""
    isolated["_apply_via_helper_v7"].side_effect = apply
    assert module.LayoutApplier.load_dconf_safely(DATA)[0]


def test_flock_failure_prevents_preflight(isolated, monkeypatch):
    monkeypatch.setattr(module.fcntl, "flock", Mock(side_effect=OSError("lock unavailable")))
    ok, message = module.LayoutApplier.load_dconf_safely(DATA)
    assert not ok
    assert "lock unavailable" in message
    isolated["ensure_available"].assert_not_called()


def test_reentrant_apply_is_rejected(isolated):
    def apply(*args, **kwargs):
        ok, message = module.LayoutApplier.load_dconf_safely(DATA)
        assert not ok
        assert "in progress" in message
        return True, ""
    isolated["_apply_via_helper_v7"].side_effect = apply
    assert module.LayoutApplier.load_dconf_safely(DATA)[0]
    isolated["ensure_available"].assert_called_once()
