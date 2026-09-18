# SPDX-License-Identifier: MIT
"""Require a backup and bind Undo to the operation that created it."""

from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest.mock import Mock

import pytest

from ui import page_layouts as module


@pytest.fixture
def page(monkeypatch):
    monkeypatch.setattr(module, "tr", lambda value: value)
    monkeypatch.setattr(module, "Gtk", Mock())
    monkeypatch.setattr(module, "Adw", Mock())
    monkeypatch.setattr(module.LayoutApplier, "last_apply_staged", False)
    monkeypatch.setattr(module.LayoutApplier, "last_apply_cleanroom", True)
    root = SimpleNamespace(_toast_overlay=Mock())
    page = SimpleNamespace(
        _active_layout="BigGnome", get_root=lambda: root,
        _layout_id=lambda cfg: Path(cfg).stem, _icon_path_for=lambda name: None,
        _toast=Mock(), _set_status=Mock(), rebuild_grid=Mock(),
        _save_current_snapshot=Mock(), _apply=Mock(), _undo_layout=Mock(),
        _prefs=Mock(last_error=""), _pool=Mock(), _done=Mock(),
    )
    page._prefs.set.return_value = True
    return page


def respond(page, label):
    buttons = {}

    def button(**kwargs):
        widget = Mock()
        buttons[kwargs["label"]] = widget
        return widget

    module.Gtk.Button.side_effect = button
    module.LayoutsPage._on_click(page, "Desk UX", "desk-ux.txt")
    callback = buttons[label].connect.call_args.args[1]
    callback(buttons[label])


@pytest.mark.parametrize("response", ["Apply", "Apply original", "Resume my changes"])
def test_backup_failure_stops_apply_and_snapshot(page, monkeypatch, response):
    monkeypatch.setattr(module.SnapshotManager, "has", lambda layout: response != "Apply")
    monkeypatch.setattr(module.BackupManager, "create", lambda: (False, "disk full"))
    respond(page, response)
    page._toast.assert_called_once_with("Backup failed: disk full")
    page._apply.assert_not_called()
    page._save_current_snapshot.assert_not_called()
    page._prefs.set.assert_not_called()
    assert page._active_layout == "BigGnome"


def test_cancel_does_not_create_backup(page, monkeypatch):
    monkeypatch.setattr(module.SnapshotManager, "has", lambda layout: False)
    backup = Mock()
    monkeypatch.setattr(module.BackupManager, "create", backup)
    respond(page, "Cancel")
    backup.assert_not_called()
    page._apply.assert_not_called()


@pytest.mark.parametrize("response", ["Apply", "Apply original", "Resume my changes"])
@pytest.mark.parametrize("reapply", [False, True])
def test_confirmation_passes_its_backup_and_preserves_snapshot_policy(
    page, monkeypatch, tmp_path, response, reapply
):
    backup = tmp_path / "own.dconf"
    page._active_layout = "Desk UX" if reapply else "BigGnome"
    monkeypatch.setattr(module.SnapshotManager, "has", lambda layout: response != "Apply")
    monkeypatch.setattr(module.BackupManager, "create", lambda: (True, str(backup)))
    respond(page, response)
    page._apply.assert_called_once_with(
        "Desk UX", "desk-ux.txt", use_snapshot=response == "Resume my changes",
        backup_path=backup,
    )
    assert page._save_current_snapshot.call_count == (0 if reapply else 1)


@pytest.mark.parametrize("snapshot", [False, True])
@pytest.mark.parametrize("outcome", ["success", "failure", "exception", "missing"])
def test_worker_retains_operation_backup(page, monkeypatch, tmp_path, snapshot, outcome):
    backup = tmp_path / "own.dconf"
    page._pool.submit.side_effect = lambda task: task()
    monkeypatch.setattr(module.GLib, "idle_add", lambda callback, *args: callback(*args))
    monkeypatch.setattr(module, "find_file",
                        lambda *args: None if outcome == "missing" else tmp_path)
    monkeypatch.setattr(module.SnapshotManager, "read",
                        lambda layout: "" if outcome == "missing" else "snapshot")
    monkeypatch.setattr(module.LayoutApplier, "_enabled_extensions", lambda: [])
    backend = Mock(return_value=(outcome == "success", "result"))
    if outcome == "exception":
        backend.side_effect = OSError("test failure")
    monkeypatch.setattr(module.LayoutApplier, "apply", backend)
    monkeypatch.setattr(module.LayoutApplier, "load_dconf_safely", backend)
    module.LayoutsPage._apply(
        page, "Desk UX", "desk-ux.txt", use_snapshot=snapshot, backup_path=backup
    )
    page._done.assert_called_once()
    args = page._done.call_args.args
    assert args[0] == "Desk UX"
    assert args[1] is (outcome == "success")
    assert args[-1] == backup


def test_undo_uses_own_backup_even_after_another_operation(page, monkeypatch, tmp_path):
    own, later = tmp_path / "own.dconf", tmp_path / "later.dconf"
    latest = Mock(return_value=later)
    monkeypatch.setattr(module.BackupManager, "latest", latest)
    module.LayoutsPage._done(page, "Desk UX", True, "", backup_path=own)
    toast = page.get_root()._toast_overlay.add_toast.call_args.args[0]
    callback = toast.connect.call_args.args[1]
    callback(toast)
    page._undo_layout.assert_called_once_with("BigGnome", own)
    latest.assert_not_called()


def test_completion_without_own_backup_does_not_offer_unrelated_undo(page, monkeypatch):
    latest = Mock(return_value=Path("unrelated.dconf"))
    monkeypatch.setattr(module.BackupManager, "latest", latest)
    module.LayoutsPage._done(page, "Desk UX", True, "")
    module.Adw.Toast.assert_not_called()
    page._toast.assert_called_once_with("Desk UX applied")
    latest.assert_not_called()


def test_failed_apply_does_not_offer_undo(page, tmp_path):
    module.LayoutsPage._done(page, "Desk UX", False, "failed", backup_path=tmp_path / "own")
    module.Adw.Toast.assert_not_called()
    assert page._active_layout == "BigGnome"


def test_undo_failure_keeps_active_layout(page, monkeypatch, tmp_path):
    own = tmp_path / "own.dconf"
    page._pool.submit.side_effect = lambda task: task()
    page._undo_failed = MethodType(module.LayoutsPage._undo_failed, page)
    page._done_undo = Mock()
    monkeypatch.setattr(module.GLib, "idle_add", lambda callback, *args: callback(*args))
    restore = Mock(return_value=(False, "backup file not found"))
    monkeypatch.setattr(module.BackupManager, "restore", restore)
    module.LayoutsPage._undo_layout(page, "Classic", own)
    restore.assert_called_once_with(own)
    page._done_undo.assert_not_called()
    assert page._active_layout == "BigGnome"
