# SPDX-License-Identifier: MIT
"""Bound icon reads and publish complete immutable overlays under contention."""

import os
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import folder_accent as module

SVG = '<svg><style>.ColorScheme-Highlight {color:#3584e4;}</style></svg>'


@pytest.fixture
def theme(tmp_path):
    root = tmp_path / "source"
    places = root / module.BASES[0] / "scalable/places"
    places.mkdir(parents=True)
    (places / "folder.svg").write_text(SVG)
    (places / "folder-documents.svg").symlink_to("folder.svg")
    (places / "user-trash.svg").write_text(SVG)
    (places.parent.parent / "index.theme").write_text(
        "[Icon Theme]\nDirectories=scalable/places\n"
        "[scalable/places]\nContext=Places\nSize=48\nType=Scalable\n"
    )
    return root, tmp_path / "output"


def build(theme, accent="orange"):
    root, output = theme
    return module.build_theme(module.BASES[0], accent, [root], output)


@pytest.mark.parametrize("relative", ["index.theme", "scalable/places/folder.svg"])
def test_oversized_input_never_publishes(theme, relative):
    root, output = theme
    (root / module.BASES[0] / relative).write_bytes(b"x" * (module.MAX_FILE_BYTES + 1))
    with pytest.raises(ValueError, match="[Oo]versized"):
        build(theme)
    assert not output.exists()


def test_size_limit_uses_opened_file(theme, monkeypatch, tmp_path):
    root, output = theme
    icon = root / module.BASES[0] / "scalable/places/folder.svg"
    large = tmp_path / "large.svg"
    large.write_bytes(b"x" * (module.MAX_FILE_BYTES + 1))
    original_open = os.open

    def swapped_open(path, flags, *args, **kwargs):
        return original_open(large if Path(path) == icon else path, flags, *args, **kwargs)

    monkeypatch.setattr(module.os, "open", swapped_open)
    with pytest.raises(ValueError, match="[Oo]versized"):
        build(theme)
    assert icon.read_text() == SVG
    assert not output.exists()


def test_read_stays_bounded_when_file_grows(theme, monkeypatch):
    root, output = theme
    icon = root / module.BASES[0] / "scalable/places/folder.svg"
    inode = icon.stat().st_ino
    original_fstat = os.fstat

    def grow(fd):
        info = original_fstat(fd)
        if info.st_ino == inode:
            with icon.open("ab") as stream:
                stream.write(b"x" * module.MAX_FILE_BYTES)
        return info

    monkeypatch.setattr(module.os, "fstat", grow)
    with pytest.raises(ValueError, match="[Oo]versized"):
        build(theme)
    assert not output.exists()


def test_fifo_icon_is_rejected_without_blocking(theme):
    root, output = theme
    icon = root / module.BASES[0] / "scalable/places/folder.svg"
    icon.unlink()
    os.mkfifo(icon)
    result = subprocess.run(
        [sys.executable, "-c", "from folder_accent import build_theme; "
         f"from pathlib import Path; build_theme({module.BASES[0]!r}, 'red', "
         f"[Path({str(root)!r})], Path({str(output)!r}))"],
        env={**os.environ, "PYTHONPATH": str(Path(module.__file__).parent)},
        capture_output=True, text=True, timeout=3,
    )
    assert result.returncode != 0
    assert "Invalid or oversized" in result.stderr
    assert not output.exists()


@pytest.mark.parametrize("kind", ["root-link", "directory-link", "file-link", "missing", "huge"])
def test_reuse_rejects_invalid_managed_content(theme, tmp_path, kind):
    result = build(theme)
    target = theme[1] / result["theme"]
    icon = target / "scalable/places/folder.svg"
    if kind == "root-link":
        moved = tmp_path / "moved"
        target.rename(moved)
        target.symlink_to(moved, target_is_directory=True)
    elif kind == "directory-link":
        moved = tmp_path / "moved"
        (target / "scalable").rename(moved)
        (target / "scalable").symlink_to(moved, target_is_directory=True)
    elif kind == "file-link":
        data = icon.read_bytes()
        icon.unlink()
        moved = tmp_path / "moved.svg"
        moved.write_bytes(data)
        icon.symlink_to(moved)
    elif kind == "missing":
        icon.unlink()
    else:
        icon.write_bytes(b"x" * (module.MAX_FILE_BYTES + 1))
    with pytest.raises(ValueError, match="collision"):
        build(theme)
    assert not list(theme[1].glob(".bgc-folders-*"))


@pytest.mark.parametrize("winner", ["complete", "edited", "missing", "empty", "symlink"])
def test_concurrent_winner_is_verified_before_reuse(theme, monkeypatch, tmp_path, winner):
    publish = module._publish_directory

    def race(source, target):
        if winner == "empty":
            target.mkdir()
        elif winner == "symlink":
            elsewhere = tmp_path / "elsewhere"
            shutil.copytree(source, elsewhere)
            target.symlink_to(elsewhere, target_is_directory=True)
        else:
            shutil.copytree(source, target)
            if winner == "edited":
                (target / "index.theme").write_text("custom edit")
            elif winner == "missing":
                (target / "scalable/places/folder.svg").unlink()
        publish(source, target)

    monkeypatch.setattr(module, "_publish_directory", race)
    if winner == "complete":
        result = build(theme)
        assert result["status"] == "ready"
        assert module.ACCENT_COLORS["orange"] in (
            theme[1] / result["theme"] / "scalable/places/folder.svg"
        ).read_text()
    else:
        with pytest.raises(ValueError, match="collision"):
            build(theme)
    assert not list(theme[1].glob(".bgc-folders-*"))
    targets = list(theme[1].iterdir())
    assert len(targets) == 1
    if winner == "empty":
        assert list(targets[0].iterdir()) == []
    elif winner == "edited":
        assert (targets[0] / "index.theme").read_text() == "custom edit"
    elif winner == "symlink":
        assert targets[0].is_symlink()


def test_simultaneous_publishers_share_one_complete_overlay(theme, monkeypatch):
    publish = module._publish_directory
    barrier = threading.Barrier(6)

    def together(source, target):
        barrier.wait(timeout=10)
        publish(source, target)

    monkeypatch.setattr(module, "_publish_directory", together)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda value: build(theme), range(6)))
    assert all(result == results[0] for result in results)
    assert [path.name for path in theme[1].iterdir()] == [results[0]["theme"]]
    assert build(theme) == results[0]
    assert (theme[0] / module.BASES[0] / "scalable/places/folder.svg").read_text() == SVG


@pytest.mark.parametrize("failure", ["file-write", "index-write", "publish"])
def test_failed_publication_keeps_previous_theme_and_cleans_stage(theme, monkeypatch, failure):
    previous = build(theme, "green")
    target = theme[1] / previous["theme"]
    original = {path.relative_to(target): path.read_bytes() for path in target.rglob("*")
                if path.is_file()}
    write = Path.write_bytes

    def failed_write(path, data):
        if (path.name == "index.theme") == (failure == "index-write"):
            raise OSError("injected write failure")
        return write(path, data)

    def failed_publish(*args):
        raise PermissionError("injected publish failure")

    with monkeypatch.context() as patcher:
        if failure == "publish":
            patcher.setattr(module, "_publish_directory", failed_publish)
        else:
            patcher.setattr(Path, "write_bytes", failed_write)
        with pytest.raises(OSError, match="injected"):
            build(theme)
    assert list(theme[1].iterdir()) == [target]
    assert all((target / relative).read_bytes() == data for relative, data in original.items())
    assert build(theme)["status"] == "ready"


@pytest.mark.parametrize("configured", [None, "", "relative", "~/data", "/absolute", "/spaces "])
def test_icon_data_home_defaults_to_absolute_path(tmp_path, monkeypatch, configured):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    if configured is None:
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    else:
        monkeypatch.setenv("XDG_DATA_HOME", configured)
    expected = Path(configured) if configured and configured.startswith("/") else (
        tmp_path / ".local/share"
    )
    assert module._data_home() == expected
    assert module.icon_roots()[1] == expected / "icons"


@pytest.mark.parametrize("configured,expected", [
    (None, ["/usr/local/share/icons", "/usr/share/icons"]),
    ("", ["/usr/local/share/icons", "/usr/share/icons"]),
    ("relative:~/data", []),
    (":/first:relative:/second:/first:", ["/first/icons", "/second/icons"]),
])
def test_icon_system_roots_preserve_absolute_precedence(
    tmp_path, monkeypatch, configured, expected
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    if configured is None:
        monkeypatch.delenv("XDG_DATA_DIRS", raising=False)
    else:
        monkeypatch.setenv("XDG_DATA_DIRS", configured)
    assert module.icon_roots()[2:] == [Path(value) for value in expected]
