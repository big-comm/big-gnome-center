# SPDX-License-Identifier: MIT
"""Snapshots never capture layout mutations or alias unrelated IDs."""

import fcntl
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock

import pytest

import layout_applier
import snapshot_manager as module
from constants import LAYOUTS

DATA = (
    "[org/gnome/shell]\nenabled-extensions=@as []\n"
    "favorite-apps=['org.gnome.Nautilus.desktop']\n\n"
    "[org/communitybig/layout-switcher/runtime]\nactive-layout='Desk UX'\n"
)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    settings = tmp_path / "dconf/settings.gnome"
    lock_path = settings.with_name("big-gnome-center-layout.lock")
    marker = tmp_path / "sync.lock"
    snapshots = tmp_path / "snapshots"

    class Store:
        def __init__(self):
            self.marker = marker
            self.state = {}

        @contextmanager
        def lock(self):
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            with lock_path.open("a") as stream:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                yield

        def read(self):
            return self.state

    store = Store()
    monkeypatch.setattr(module, "SNAPSHOTS_DIR", snapshots)
    monkeypatch.setattr(module, "SETTINGS_GNOME", settings)
    monkeypatch.setattr(module, "open_store", Mock(return_value=store))
    monkeypatch.setattr(module, "run_cmd", Mock(return_value=(True, DATA)))
    monkeypatch.setattr(layout_applier, "_LAYOUT_MUTATION_LOCK_PATH", lock_path)
    monkeypatch.setattr("settings_store.CONFIG_DIR", tmp_path / "config")
    monkeypatch.setattr("settings_store.SETTINGS_FILE", tmp_path / "config/settings.json")
    return store


@pytest.mark.parametrize("layout_id", [Path(cfg).stem for name, cfg, *rest in LAYOUTS])
def test_canonical_paths_keep_existing_snapshots(isolated, layout_id):
    path = module.SNAPSHOTS_DIR / f"{layout_id}.dconf"
    path.parent.mkdir()
    path.write_text(DATA)
    assert module.SnapshotManager.load(layout_id) == path
    assert module.SnapshotManager.read(layout_id) == DATA


@pytest.mark.parametrize("left,right", [
    ("custom one", "customone"), ("a.b", "ab"), ("../classic", "classic"),
    ("A", "a"), ("!!!", "???"), ("á", "a"), ("x" * 400, "x" * 401),
])
def test_distinct_ids_never_alias(isolated, left, right):
    data = DATA.replace("Desk UX", "Classic") if right == "classic" else DATA
    module.run_cmd.return_value = True, data
    paths = []
    for identifier in (left, right):
        ok, info = module.SnapshotManager.save(identifier)
        assert ok, info
        path = Path(info)
        assert path.parent == module.SNAPSHOTS_DIR
        assert len(path.name.encode()) <= 255
        paths.append(path)
    assert paths[0] != paths[1]
    assert module.SnapshotManager.delete(left)
    assert module.SnapshotManager.read(right) == data


@pytest.mark.parametrize("identifier", [None, "", 1, [], {}])
def test_invalid_ids_do_not_touch_storage(isolated, identifier):
    assert not module.SnapshotManager.save(identifier)[0]
    assert module.SnapshotManager.load(identifier) is None
    assert module.SnapshotManager.read(identifier) is None
    assert not module.SnapshotManager.delete(identifier)
    module.run_cmd.assert_not_called()
    assert not module.SNAPSHOTS_DIR.exists()


@pytest.mark.parametrize("condition", ["transaction", "staged", "marker", "corrupt", "protocol"])
def test_quarantined_state_preserves_snapshot_before_dump(isolated, condition):
    path = module.SNAPSHOTS_DIR / "desk-ux.dconf"
    path.parent.mkdir()
    path.write_text(DATA)
    if condition in {"transaction", "staged"}:
        isolated.state[condition] = True
    elif condition == "marker":
        isolated.marker.write_text("unknown owner")
    elif condition == "corrupt":
        isolated.read = Mock(side_effect=ValueError("corrupt journal"))
    else:
        module.open_store.side_effect = OSError("protocol missing")
    assert not module.SnapshotManager.save("desk-ux")[0]
    module.run_cmd.assert_not_called()
    assert path.read_text() == DATA
    if condition == "marker":
        assert isolated.marker.read_text() == "unknown owner"


@pytest.mark.parametrize("prefs", [{"last_apply_ok": False}, {"pending_layout": "Classic"}])
def test_fresh_preferences_guard_capture(isolated, prefs):
    import settings_store

    settings_store.CONFIG_DIR.mkdir()
    settings_store.SETTINGS_FILE.write_text(json.dumps(prefs))
    assert not module.SnapshotManager.save("desk-ux")[0]
    module.run_cmd.assert_not_called()


def test_mismatched_active_layout_preserves_previous_snapshot(isolated):
    path = module.SNAPSHOTS_DIR / "classic.dconf"
    path.parent.mkdir()
    path.write_text(DATA.replace("Desk UX", "Classic"))
    assert not module.SnapshotManager.save("classic")[0]
    assert "Classic" in path.read_text()


def test_snapshot_without_runtime_metadata_remains_supported(isolated):
    data = DATA.split("[org/communitybig")[0] + "# legacy snapshot\n"
    module.run_cmd.return_value = True, data
    assert module.SnapshotManager.save("classic")[0]
    assert module.SnapshotManager.read("classic") == data


def test_save_and_delete_reject_mutation_lock(isolated):
    preflight = Mock(return_value=(True, ""))
    guarded = layout_applier._serialized_layout_switch(preflight)
    with isolated.lock():
        assert not module.SnapshotManager.save("desk-ux")[0]
        assert not module.SnapshotManager.delete("desk-ux")
        assert not guarded()[0]
    module.run_cmd.assert_not_called()
    preflight.assert_not_called()
    assert module.SnapshotManager.save("desk-ux")[0]
    assert guarded()[0]


def test_snapshot_holds_mutation_lock_through_publication(isolated, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    write = module.atomic_write_text

    def delayed(path, data):
        entered.set()
        assert release.wait(10)
        write(path, data)

    monkeypatch.setattr(module, "atomic_write_text", delayed)
    preflight = Mock(return_value=(True, ""))
    guarded = layout_applier._serialized_layout_switch(preflight)
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(module.SnapshotManager.save, "desk-ux")
        try:
            assert entered.wait(10)
            assert not guarded()[0]
            assert not module.SnapshotManager.save("desk-ux")[0]
            assert not module.SnapshotManager.delete("desk-ux")
            preflight.assert_not_called()
        finally:
            release.set()
        assert result.result(timeout=10)[0]
    assert guarded()[0]
    assert module.SnapshotManager.read("desk-ux") == DATA


def test_dump_already_holds_shared_lock(isolated):
    preflight = Mock(return_value=(True, ""))
    guarded = layout_applier._serialized_layout_switch(preflight)

    def capture(*args, **kwargs):
        assert not guarded()[0]
        preflight.assert_not_called()
        return True, DATA

    module.run_cmd.side_effect = capture
    assert module.SnapshotManager.save("desk-ux")[0]
    assert guarded()[0]


@pytest.mark.parametrize("failure", ["dump", "tiny", "invalid", "replace", "lock"])
def test_failed_capture_preserves_previous_snapshot_and_releases_lock(
    isolated, monkeypatch, failure
):
    path = module.SNAPSHOTS_DIR / "desk-ux.dconf"
    path.parent.mkdir()
    path.write_text(DATA)
    with monkeypatch.context() as failure_patch:
        if failure == "dump":
            module.run_cmd.return_value = False, "dump failed"
        elif failure == "tiny":
            module.run_cmd.return_value = True, "tiny"
        elif failure == "invalid":
            module.run_cmd.return_value = True, "invalid data" * 20
        elif failure == "replace":
            failure_patch.setattr("utils.os.replace", Mock(side_effect=OSError("disk full")))
        else:
            failure_patch.setattr(isolated, "lock", Mock(side_effect=OSError("lock denied")))
        assert not module.SnapshotManager.save("desk-ux")[0]
        assert path.read_text() == DATA
        assert list(path.parent.iterdir()) == [path]
    module.run_cmd.return_value = True, DATA
    assert module.SnapshotManager.save("desk-ux")[0]


def test_read_rejects_directory_and_tiny_content(isolated):
    path = module.SNAPSHOTS_DIR / "desk-ux.dconf"
    path.mkdir(parents=True)
    assert module.SnapshotManager.load("desk-ux") is None
    assert module.SnapshotManager.read("desk-ux") is None
    path.rmdir()
    path.write_text("tiny")
    assert module.SnapshotManager.read("desk-ux") is None
