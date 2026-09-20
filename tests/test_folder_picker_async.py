"""GTK responsiveness, request retirement and batched folder choices."""

import threading
import time
from pathlib import Path

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

import folder_icon_picker as picker
from folder_icons import CUSTOM_NAME, CUSTOM_URI, FolderIcon


def spin(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            pytest.fail("GTK operation timed out")
        GLib.MainContext.default().iteration(False)
        time.sleep(0.001)


def drain():
    for _ in range(100):
        if not GLib.MainContext.default().pending():
            break
        GLib.MainContext.default().iteration(False)


def icons(count=65, prefix="folder"):
    return [FolderIcon(f"{prefix}-{i}", f"Design {i}", Path(f"/{prefix}-{i}.svg"),
                       (f"{prefix}-{i}",)) for i in range(count)]


@pytest.fixture(scope="module")
def picker_app():
    if not Gtk.init_check() or Gdk.Display.get_default() is None:
        pytest.skip("Requires a GTK display")
    Adw.init()
    app = Adw.Application(application_id="org.communitybig.FolderAsyncTest",
                          flags=Gio.ApplicationFlags.NON_UNIQUE)
    app.register(None)
    return app


@pytest.fixture
def ui(monkeypatch, tmp_path, picker_app):
    windows, releases = [], []
    monkeypatch.setattr(picker, "read_metadata", lambda *_: {CUSTOM_URI: None, CUSTOM_NAME: None})
    monkeypatch.setattr(picker, "available_icons", lambda *a, **k: icons())

    def make():
        window = picker.FolderIconWindow(picker_app, Gio.File.new_for_path(str(tmp_path)))
        window.realize()
        windows.append(window)
        return window

    yield make, releases
    for release in releases:
        release.set()
    for window in windows:
        window._destroyed(window)
        window.destroy()
    spin(lambda: all(not w._worker_running for w in windows))
    drain()


@pytest.mark.parametrize("operation", ["metadata", "catalog", "recognition"])
def test_initial_disk_work_keeps_gtk_responsive(ui, monkeypatch, operation):
    make, releases = ui
    entered, release = threading.Event(), threading.Event()
    releases.append(release)
    names = {"metadata": "read_metadata", "catalog": "available_icons",
             "recognition": "selected_icon"}
    original = getattr(picker, names[operation])
    worker_threads = []

    def delayed(*args, **kwargs):
        worker_threads.append(threading.get_ident())
        entered.set()
        release.wait(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(picker, names[operation], delayed)
    started = time.monotonic()
    window = make()
    assert time.monotonic() - started < 0.5
    spin(entered.is_set)
    heartbeat = []
    GLib.idle_add(lambda: heartbeat.append(True) or GLib.SOURCE_REMOVE)
    spin(lambda: bool(heartbeat))
    assert not window.apply.get_sensitive() and window.cancel.get_sensitive()
    assert worker_threads == [worker_threads[0]] and worker_threads[0] != threading.get_ident()
    release.set()
    spin(lambda: not window._loading)
    assert len(window.choices) == 65


def test_latest_folder_request_wins_and_pending_work_is_coalesced(ui, monkeypatch, tmp_path):
    make, releases = ui
    entered, release = threading.Event(), threading.Event()
    releases.append(release)
    calls = []

    def metadata(folder, cancel):
        calls.append(folder.get_basename())
        if len(calls) == 1:
            entered.set()
            release.wait(1)
        return {CUSTOM_URI: None, CUSTOM_NAME: "folder-50"}

    monkeypatch.setattr(picker, "read_metadata", metadata)
    window = make()
    spin(entered.is_set)
    for index in range(25):
        window.folder = Gio.File.new_for_path(str(tmp_path / f"new-{index}"))
        window._reload()
    release.set()
    spin(lambda: not window._loading)
    assert calls == [tmp_path.name, "new-24"]
    assert window._metadata_folder == window.folder.get_uri()
    assert window._selected == "folder-50"


def test_close_retires_delayed_completion(ui, monkeypatch):
    make, releases = ui
    entered, release = threading.Event(), threading.Event()
    releases.append(release)

    def delayed(*args, **kwargs):
        entered.set()
        release.wait(1)
        raise OSError("obsolete failure")

    monkeypatch.setattr(picker, "available_icons", delayed)
    window = make()
    spin(entered.is_set)
    window._destroyed(window)
    label = window.message.get_label()
    release.set()
    spin(lambda: not window._worker_running)
    drain()
    assert window.message.get_label() == label
    assert not window._completion_sources and not window._build_source
    assert window.grid.get_first_child() is None


def test_grid_is_batched_and_new_request_retires_old_tiles(ui, monkeypatch):
    make, _ = ui
    monkeypatch.setattr(picker, "available_icons", lambda *a, **k: icons(205, "old"))
    window = make()
    spin(lambda: getattr(window, "_build_index", 0) > 0)
    assert window._build_index <= picker.GRID_BATCH_SIZE
    assert window._loading
    monkeypatch.setattr(picker, "available_icons", lambda *a, **k: icons(45, "new"))
    window._reload()
    spin(lambda: not window._loading)
    names = []
    child = window.grid.get_first_child()
    while child:
        names.append(child.icon_name)
        child = child.get_next_sibling()
    assert names == [icon.name for icon in icons(45, "new")]


def test_selection_and_search_survive_reload_without_refreshing_metadata(ui, monkeypatch):
    make, _ = ui
    window = make()
    spin(lambda: not window._loading)
    window.grid.select_child(window.grid.get_child_at_index(50))
    monkeypatch.setattr(picker, "read_metadata", lambda *_: pytest.fail("metadata rebased"))
    window._reload()
    spin(lambda: not window._loading)
    assert window._selected == "folder-50" and window.apply.get_sensitive()
    window.search.set_text("Design 2")
    window._search_changed(window.search)
    assert window._selected is None and not window.apply.get_sensitive()
    window._reload()
    spin(lambda: not window._loading)
    assert window._selected is None


@pytest.mark.parametrize("operation", ["metadata", "catalog"])
def test_load_failure_is_visible_and_cannot_save(ui, monkeypatch, operation):
    make, _ = ui

    def unavailable(*args, **kwargs):
        raise OSError("unavailable test location")

    monkeypatch.setattr(picker, "read_metadata" if operation == "metadata" else "available_icons",
                        unavailable)
    window = make()
    spin(lambda: not window._loading)
    assert "unavailable" in window.message.get_label()
    assert not window.apply.get_sensitive() and not window.restore.get_sensitive()
    assert window.cancel.get_sensitive()


def test_close_cancels_partial_grid(ui, monkeypatch):
    make, _ = ui
    monkeypatch.setattr(picker, "available_icons", lambda *a, **k: icons(205))
    window = make()
    spin(lambda: getattr(window, "_build_index", 0) > 0)
    count = window._build_index
    window._destroyed(window)
    drain()
    assert window._build_index == count and not window._build_source


def test_new_folder_uses_its_metadata_selection(ui, monkeypatch, tmp_path):
    make, _ = ui
    window = make()
    spin(lambda: not window._loading)
    window.grid.select_child(window.grid.get_child_at_index(10))
    monkeypatch.setattr(picker, "read_metadata",
                        lambda *_: {CUSTOM_URI: None, CUSTOM_NAME: "folder-50"})
    window.folder = Gio.File.new_for_path(str(tmp_path / "another"))
    window._reload()
    spin(lambda: not window._loading)
    assert window._selected == "folder-50"


def test_queued_old_completion_cannot_publish_after_reload(ui, monkeypatch):
    make, _ = ui
    window = make()
    deadline = time.monotonic() + 2
    while window._worker_running and time.monotonic() < deadline:
        time.sleep(0.001)
    assert window._completion_sources
    monkeypatch.setattr(picker, "available_icons", lambda *a, **k: icons(25, "latest"))
    window._reload()
    spin(lambda: not window._loading)
    assert [icon.name for icon in window.choices] == [icon.name for icon in icons(25, "latest")]
    assert not window._completion_sources


def test_save_failure_survives_deferred_theme_reload(ui, monkeypatch):
    make, releases = ui
    entered, release = threading.Event(), threading.Event()
    releases.append(release)
    window = make()
    spin(lambda: not window._loading)
    window.grid.select_child(window.grid.get_child_at_index(50))
    captured = []

    def save(folder, name, metadata):
        captured.append((folder, name, metadata))
        entered.set()
        release.wait(1)
        raise OSError("test write failed")

    monkeypatch.setattr(picker, "save_icon", save)
    window._save(window._selected)
    spin(entered.is_set)
    assert window._close_requested(window) is True
    window._reload()
    release.set()
    spin(lambda: not window._busy and not window._loading)
    assert window.message.get_label() == "test write failed"
    assert window._selected == "folder-50"
    assert captured[0][2] == window._metadata and captured[0][2] is not window._metadata


def test_thread_start_failure_recovers_controls(ui, monkeypatch):
    make, _ = ui

    def fail(_self):
        raise RuntimeError("thread unavailable")

    monkeypatch.setattr(picker.threading.Thread, "start", fail)
    window = make()
    assert not window._loading and not window._worker_running
    assert window.cancel.get_sensitive() and "thread unavailable" in window.message.get_label()
