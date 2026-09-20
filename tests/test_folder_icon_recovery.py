"""Readback and ownership checks for folder metadata writes."""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from gi.repository import Gio

import folder_icons as model
from folder_accent import MAX_FILE_BYTES
from tests.test_folder_icons import SVG, Folder

ORIGINAL = {model.CUSTOM_URI: "file:///personal.svg", model.CUSTOM_NAME: "folder-cloud"}


@pytest.mark.parametrize("name", [None, "folder-git"])
@pytest.mark.parametrize("failed_write", [1, 2])
@pytest.mark.parametrize("mode", ["silent", "changed-before-false"])
def test_incomplete_writes_are_verified_and_recovered(name, failed_write, mode):
    class Faulty(Folder):
        def set_attribute_string(self, key, value, *args):
            if len(self.writes) + 1 == failed_write:
                self.writes.append((key, value))
                if mode == "changed-before-false":
                    self.metadata[key] = value
                    return False
                return True
            return super().set_attribute_string(key, value, *args)

    folder = Faulty(ORIGINAL)
    with pytest.raises(OSError):
        model.save_icon(folder, name, ORIGINAL.copy())
    assert folder.metadata == ORIGINAL


@pytest.mark.parametrize("external_key", model.ATTRIBUTES)
def test_concurrent_metadata_survives_recovery(external_key):
    class Concurrent(Folder):
        def set_attribute_string(self, key, value, *args):
            result = super().set_attribute_string(key, value, *args)
            if len(self.writes) == 1:
                self.metadata[external_key] = "external-edit"
            return result

    folder = Concurrent(ORIGINAL)
    with pytest.raises((OSError, ValueError)):
        model.save_icon(folder, "folder-git", ORIGINAL.copy())
    assert folder.metadata[external_key] == "external-edit"
    other = next(key for key in model.ATTRIBUTES if key != external_key)
    assert folder.metadata[other] == ORIGINAL[other]


@pytest.mark.parametrize("silent_rollback", [False, True])
def test_failed_rollback_does_not_prevent_independent_recovery(silent_rollback):
    class Faulty(Folder):
        failed_read = False

        def query_info(self, *args):
            if len(self.writes) == 2 and not self.failed_read:
                self.failed_read = True
                raise OSError("readback failed")
            return super().query_info(*args)

        def set_attribute_string(self, key, value, *args):
            if len(self.writes) == 2:
                self.writes.append((key, value))
                return silent_rollback
            return super().set_attribute_string(key, value, *args)

    folder = Faulty(ORIGINAL)
    with pytest.raises(OSError, match=model.tr("Could not restore the previous folder icon.")):
        model.save_icon(folder, "folder-git", ORIGINAL.copy())
    assert folder.metadata == {model.CUSTOM_URI: None, model.CUSTOM_NAME: "folder-cloud"}
    assert folder.writes[-1] == (model.CUSTOM_NAME, "folder-cloud")


def test_external_edit_between_attribute_writes_is_not_overwritten():
    class Concurrent(Folder):
        queries = 0

        def query_info(self, *args):
            self.queries += 1
            if self.queries == 4:
                self.metadata[model.CUSTOM_URI] = "file:///external.svg"
            return super().query_info(*args)

    folder = Concurrent(ORIGINAL)
    with pytest.raises(ValueError):
        model.save_icon(folder, "folder-git", ORIGINAL.copy())
    assert folder.metadata == {
        model.CUSTOM_NAME: ORIGINAL[model.CUSTOM_NAME],
        model.CUSTOM_URI: "file:///external.svg",
    }
    assert all(key != model.CUSTOM_URI for key, _ in folder.writes)


def places(tmp_path):
    directory = tmp_path / model.BASES[0] / "scalable/places"
    directory.mkdir(parents=True)
    return directory


def test_svg_read_limit_survives_stale_size(tmp_path, monkeypatch, caplog):
    directory = places(tmp_path)
    (directory / "folder-big.svg").write_bytes(SVG.encode() + b" " * MAX_FILE_BYTES)
    original_fstat = os.fstat
    original_stat = Path.stat

    def stale_size(fd):
        return SimpleNamespace(st_mode=original_fstat(fd).st_mode, st_size=1)

    monkeypatch.setattr(model.os, "fstat", stale_size)
    monkeypatch.setattr(Path, "stat", lambda path, *a, **k: (
        SimpleNamespace(st_size=1)
        if path.name == "folder-big.svg" else original_stat(path, *a, **k)
    ))
    assert model.available_icons(model.BASES[0], [tmp_path]) == []
    assert "folder-big.svg" in caplog.text and "byte limit" in caplog.text


def test_nonregular_svg_is_reported_without_blocking(tmp_path, caplog):
    directory = places(tmp_path)
    os.mkfifo(directory / "folder-pipe.svg")
    assert model.available_icons(model.BASES[0], [tmp_path]) == []
    assert "folder-pipe.svg" in caplog.text and "not a regular file" in caplog.text


def test_catalog_keeps_all_valid_choices_and_reports_exclusions(tmp_path, caplog):
    directory = places(tmp_path)
    for index in range(450):
        (directory / f"folder-{index}.svg").write_text(SVG)
    (directory / "folder-invalid.svg").write_bytes(b"\xff")
    (directory / "folder-broken.svg").symlink_to("absent.svg")
    assert len(model.available_icons(model.BASES[0], [tmp_path])) == 450
    assert "folder-invalid.svg" in caplog.text and "folder-broken.svg" in caplog.text


def test_cancelled_catalog_does_not_touch_disk(tmp_path, monkeypatch):
    cancel = Gio.Cancellable()
    cancel.cancel()
    monkeypatch.setattr(model.os, "scandir", lambda *_: pytest.fail("cancelled disk access"))
    assert model.available_icons(model.BASES[0], [tmp_path], cancellable=cancel) == []
