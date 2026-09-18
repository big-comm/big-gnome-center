# SPDX-License-Identifier: MIT
"""Native confirmation and Undo signals with a controlled layout backend."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest.mock import Mock

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk

from ui import page_layouts as module


def _button(widget, label):
    if isinstance(widget, Gtk.Button) and widget.get_label() == label:
        return widget
    child = widget.get_first_child()
    while child:
        found = _button(child, label)
        if found is not None:
            return found
        child = child.get_next_sibling()
    return None


def _until(predicate):
    deadline = time.monotonic() + 5
    context = GLib.MainContext.default()
    while not predicate() and time.monotonic() < deadline:
        context.iteration(False)
        time.sleep(0.001)
    assert predicate()


@pytest.mark.parametrize("response", ["Apply", "Apply original", "Resume my changes"])
@pytest.mark.parametrize("backup_ok", [False, True], ids=["backup-failure", "backup-success"])
def test_native_confirmation_and_undo(monkeypatch, tmp_path, response, backup_ok):
    if not Gtk.init_check() or Gdk.Display.get_default() is None:
        pytest.skip("Requires a GTK display")
    Adw.init()
    main_thread = threading.get_ident()
    own, later = tmp_path / "own.dconf", tmp_path / "later.dconf"
    entered, release = threading.Event(), threading.Event()
    toasts = []
    window = Adw.Window(title="Big Gnome Center — backup validation")
    window.set_default_size(620, 420)
    overlay = Adw.ToastOverlay()
    overlay.set_child(Gtk.Box())
    window.set_content(overlay)
    window._toast_overlay = overlay
    original_add = Adw.ToastOverlay.add_toast

    def add_toast(widget, toast):
        assert threading.get_ident() == main_thread
        toasts.append(toast)
        original_add(widget, toast)

    def backend(*args, **kwargs):
        assert threading.get_ident() != main_thread
        entered.set()
        assert release.wait(5)
        return True, ""

    monkeypatch.setattr(Adw.ToastOverlay, "add_toast", add_toast)
    monkeypatch.setattr(module, "tr", lambda text: text)
    monkeypatch.setattr(module, "find_file", lambda *args: tmp_path / "desk-ux.txt")
    monkeypatch.setattr(module.SnapshotManager, "has", lambda value: response != "Apply")
    monkeypatch.setattr(module.SnapshotManager, "read", lambda value: "snapshot")
    monkeypatch.setattr(module.BackupManager, "create",
                        lambda: (True, str(own)) if backup_ok else (False, "disk full"))
    latest = Mock(return_value=later)
    monkeypatch.setattr(module.BackupManager, "latest", latest)
    monkeypatch.setattr(module.LayoutApplier, "apply", backend)
    monkeypatch.setattr(module.LayoutApplier, "load_dconf_safely", backend)
    monkeypatch.setattr(module.LayoutApplier, "_enabled_extensions", lambda: [])
    monkeypatch.setattr(module.LayoutApplier, "last_apply_staged", False)
    monkeypatch.setattr(module.LayoutApplier, "last_apply_cleanroom", True)

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            page = SimpleNamespace(
                _pool=pool, _active_layout="BigGnome", get_root=lambda: window,
                _layout_id=lambda cfg: Path(cfg).stem, _icon_path_for=lambda name: None,
                _toast=Mock(), _set_status=Mock(), rebuild_grid=Mock(),
                _save_current_snapshot=Mock(), _undo_layout=Mock(),
                _prefs=Mock(last_error=""),
            )
            page._prefs.set.return_value = True
            page._apply = MethodType(module.LayoutsPage._apply, page)
            page._done = MethodType(module.LayoutsPage._done, page)
            window.present()
            module.LayoutsPage._on_click(page, "Desk UX", "desk-ux.txt")
            dialog = window.get_visible_dialog()
            assert dialog is not None
            button = _button(dialog.get_child(), response)
            assert button is not None
            try:
                button.emit("clicked")
                if not backup_ok:
                    assert not entered.is_set()
                    page._toast.assert_called_once_with("Backup failed: disk full")
                    page._save_current_snapshot.assert_not_called()
                    page._prefs.set.assert_not_called()
                    assert page._active_layout == "BigGnome"
                else:
                    assert entered.wait(5)
                    # Another operation replaces the latest backup before completion.
                    later.write_text("unrelated backup")
            finally:
                release.set()
            if backup_ok:
                _until(lambda: len(toasts) == 1)
                assert page._active_layout == "Desk UX"
                assert toasts[0].get_button_label() == "Undo"
                toasts[0].emit("button-clicked")
                page._undo_layout.assert_called_once_with("BigGnome", own)
                page._save_current_snapshot.assert_called_once()
            else:
                assert not toasts
            latest.assert_not_called()
    finally:
        release.set()
        if entered.is_set():
            # Drain completion even when a regression assertion failed.
            _until(lambda: bool(toasts))
        if window.get_visible_dialog() is not None:
            window.get_visible_dialog().force_close()
        window.close()
