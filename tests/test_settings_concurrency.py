# SPDX-License-Identifier: MIT
"""Protect preference updates across instances, threads and processes."""

import errno
import fcntl
import json
import multiprocessing
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import settings_store


@pytest.fixture
def settings_path(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    monkeypatch.setattr(settings_store, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", path)
    return path


@pytest.mark.parametrize("shared", [False, True])
@pytest.mark.parametrize("remove", [False, True])
def test_overlapping_updates_keep_both_changes(settings_path, shared, remove):
    settings_path.write_text(json.dumps({"keep": 1, "remove": True}))
    first = settings_store.Settings()
    second = first if shared else settings_store.Settings()
    writing, release, second_started, second_done = [threading.Event() for index in range(4)]
    write = first._write

    def held_write(data):
        if threading.current_thread().name.endswith("_0"):
            writing.set()
            assert release.wait(5)
        return write(data)

    first._write = held_write

    def update_second():
        second_started.set()
        try:
            return second.set("second", 2)
        finally:
            second_done.set()

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="settings-test") as pool:
        first_job = (
            pool.submit(first.delete, "remove") if remove else pool.submit(first.set, "first", 1)
        )
        try:
            assert writing.wait(5)
            second_job = pool.submit(update_second)
            assert second_started.wait(5)
            assert not second_done.wait(0.2), "Second update overtook an unpublished write"
        finally:
            release.set()
        assert first_job.result(timeout=5)
        assert second_job.result(timeout=5)
    expected = {"keep": 1, "second": 2}
    if not remove:
        expected.update({"remove": True, "first": 1})
    assert json.loads(settings_path.read_text()) == expected


def _process_writer(directory, barrier, worker):
    settings_store.CONFIG_DIR = Path(directory)
    settings_store.SETTINGS_FILE = Path(directory) / "settings.json"
    prefs = settings_store.Settings()
    write = prefs._write

    def delayed_write(data):
        time.sleep(0.003)
        return write(data)

    prefs._write = delayed_write
    barrier.wait(timeout=15)
    for index in range(25):
        assert prefs.set(f"worker-{worker}-{index}", index), prefs.last_error
        assert prefs.delete(f"obsolete-{worker}-{index}"), prefs.last_error


def _process_reader(directory, ready, stop, observations):
    settings_store.CONFIG_DIR = Path(directory)
    settings_store.SETTINGS_FILE = Path(directory) / "settings.json"
    expected = {"menu": False, "layout": "desk-ux"}
    count = 0
    while not stop.is_set():
        data = json.loads(settings_store.SETTINGS_FILE.read_text())
        assert data["preserved"] == expected
        assert settings_store.Settings().get("preserved") == expected
        count += 1
        ready.set()
        time.sleep(0.001)
    observations.value = count


def test_process_updates_preserve_unrelated_values_and_deletions(settings_path):
    initial = {"preserved": {"menu": False, "layout": "desk-ux"}}
    for worker in range(4):
        for index in range(25):
            initial[f"obsolete-{worker}-{index}"] = True
    settings_path.write_text(json.dumps(initial))
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(4)
    ready, stop = context.Event(), context.Event()
    observations = context.Value("i", 0)
    reader = context.Process(target=_process_reader,
                             args=(str(settings_path.parent), ready, stop, observations))
    children = [context.Process(target=_process_writer,
                               args=(str(settings_path.parent), barrier, worker))
                for worker in range(4)]
    try:
        reader.start()
        assert ready.wait(10)
        for child in children:
            child.start()
        for child in children:
            child.join(timeout=30)
            assert child.exitcode == 0
        stop.set()
        reader.join(timeout=10)
        assert reader.exitcode == 0
        assert observations.value > 1
    finally:
        stop.set()
        for child in [reader, *children]:
            if child.is_alive():
                child.terminate()
                child.join(timeout=5)
    expected = {"preserved": initial["preserved"]}
    expected.update({f"worker-{worker}-{index}": index
                     for worker in range(4) for index in range(25)})
    assert json.loads(settings_path.read_text()) == expected


@pytest.mark.parametrize("remove", [False, True])
def test_lock_failure_preserves_preferences(settings_path, monkeypatch, remove):
    prefs = settings_store.Settings()
    assert prefs.set("key", "before")
    original = settings_path.read_bytes()

    def reject_lock(descriptor, operation):
        raise PermissionError("lock denied")

    with monkeypatch.context() as scoped:
        scoped.setattr(fcntl, "flock", reject_lock)
        result = prefs.delete("key") if remove else prefs.set("key", "after")
        assert result is False
        assert "lock denied" in prefs.last_error
        assert prefs.get("key") == "before"
        assert settings_path.read_bytes() == original
    assert prefs.set("key", "after")
    assert not prefs.last_error


def _hold_lock(path, ready):
    with open(path, "a", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        ready.set()
        time.sleep(30)


def test_terminated_writer_releases_persistent_lock(settings_path):
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    lock_path = settings_path.with_name(settings_path.name + ".lock")
    child = context.Process(target=_hold_lock, args=(str(lock_path), ready))
    child.start()
    try:
        assert ready.wait(10)
        inode = lock_path.stat().st_ino
        child.terminate()
        child.join(timeout=5)
        assert not child.is_alive()
        prefs = settings_store.Settings()
        assert prefs.set("recovered", True)
        assert prefs.delete("missing")
        assert prefs.get("recovered") is True
        assert lock_path.stat().st_ino == inode
    finally:
        if child.is_alive():
            child.terminate()
            child.join(timeout=5)


@pytest.mark.parametrize("operation", ["create", "sync", "replace", "serialize"])
def test_publication_failure_releases_lock_and_preserves_data(
    settings_path, monkeypatch, operation,
):
    prefs = settings_store.Settings()
    assert prefs.set("key", "before")
    original = settings_path.read_bytes()
    with monkeypatch.context() as scoped:
        targets = {"create": "utils.tempfile.mkstemp", "sync": "utils.os.fsync",
                   "replace": "utils.os.replace"}
        if operation != "serialize":
            def fail(*args, **kwargs):
                raise OSError(errno.ENOSPC, "injected storage failure")
            scoped.setattr(targets[operation], fail)
        assert prefs.set("key", object() if operation == "serialize" else "after") is False
    assert prefs.last_error
    assert prefs.get("key") == "before"
    assert settings_path.read_bytes() == original
    assert not list(settings_path.parent.glob(".settings.json.*.tmp"))
    # Another writer must not inherit a leaked lock after the failed publication.
    recovered = settings_store.Settings()
    assert recovered.set("next", True)
    assert json.loads(settings_path.read_text()) == {"key": "before", "next": True}


def test_unusable_lock_path_does_not_replace_preferences(settings_path):
    settings_path.write_text('{"key": "before"}')
    lock_path = settings_path.with_name(settings_path.name + ".lock")
    lock_path.mkdir()
    prefs = settings_store.Settings()
    original = settings_path.read_bytes()
    assert prefs.set("key", "after") is False
    assert prefs.last_error
    assert prefs.get("key") == "before"
    assert settings_path.read_bytes() == original
    lock_path.rmdir()
    assert prefs.set("key", "after")
    assert not prefs.last_error


def _interrupted_publication(directory, ready):
    import utils

    settings_store.CONFIG_DIR = Path(directory)
    settings_store.SETTINGS_FILE = Path(directory) / "settings.json"
    replace = utils.os.replace

    def pause_before_publication(source, destination):
        ready.set()
        time.sleep(30)
        return replace(source, destination)

    utils.os.replace = pause_before_publication
    assert settings_store.Settings().set("unpublished", True)


def _single_process_update(directory, started, completed):
    settings_store.CONFIG_DIR = Path(directory)
    settings_store.SETTINGS_FILE = Path(directory) / "settings.json"
    started.set()
    assert settings_store.Settings().set("recovered", True)
    completed.set()


@pytest.mark.parametrize("same_directory", [True, False])
def test_interrupted_publication_recovers_without_blocking_other_profiles(
    settings_path, same_directory,
):
    settings_path.write_text('{"preserved": true}')
    context = multiprocessing.get_context("spawn")
    ready, started, completed = context.Event(), context.Event(), context.Event()
    target_dir = settings_path.parent if same_directory else settings_path.parent / "other"
    writer = context.Process(target=_interrupted_publication,
                             args=(str(settings_path.parent), ready))
    next_writer = context.Process(target=_single_process_update,
                                  args=(str(target_dir), started, completed))
    try:
        writer.start()
        assert ready.wait(10)
        assert json.loads(settings_path.read_text()) == {"preserved": True}
        next_writer.start()
        assert started.wait(10)
        if same_directory:
            assert not completed.wait(0.2)
        else:
            assert completed.wait(10), "An unrelated profile was blocked"
        writer.terminate()
        writer.join(timeout=5)
        assert not writer.is_alive()
        assert completed.wait(10)
        next_writer.join(timeout=5)
        assert next_writer.exitcode == 0
        expected = {"preserved": True, "recovered": True} if same_directory else {"preserved": True}
        assert json.loads(settings_path.read_text()) == expected
        if not same_directory:
            assert json.loads((target_dir / "settings.json").read_text()) == {"recovered": True}
    finally:
        for child in [writer, next_writer]:
            if child.is_alive():
                child.terminate()
                child.join(timeout=5)
