# SPDX-License-Identifier: MIT
"""Pacman hook that hides GNOME's Extensions app while BGC is installed."""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "usr/share/libalpm/scripts/big-gnome-center-extensions-app"
HOOKS = ROOT / "usr/share/libalpm/hooks"
DESKTOP = (
    "[Desktop Entry]\n"
    "Type=Application\n"
    "Name=Extensions\n"
    "Exec=/usr/bin/gnome-extensions-app\n"
    "DBusActivatable=true\n"
    "OnlyShowIn=GNOME;\n"
    "\n"
    "[Desktop Action example]\n"
    "Name=Example\n"
    "NoDisplay=false\n"
)


def run(path, action):
    env = {**os.environ, "BGC_EXTENSIONS_DESKTOP": str(path)}
    return subprocess.run([str(SCRIPT), action], env=env, check=True)


@pytest.fixture
def desktop(tmp_path):
    path = tmp_path / "org.gnome.Extensions.desktop"
    path.write_text(DESKTOP)
    path.chmod(0o644)
    return path


def test_hide_marks_main_group_and_show_restores_exact_file(desktop):
    run(desktop, "hide")
    lines = desktop.read_text().splitlines()
    assert lines[:3] == [
        "[Desktop Entry]", "NoDisplay=true", "X-BigGnomeCenter-Hidden=true",
    ]
    assert oct(desktop.stat().st_mode & 0o777) == "0o644"

    run(desktop, "show")
    assert desktop.read_text() == DESKTOP


def test_hide_and_show_are_idempotent(desktop):
    run(desktop, "hide")
    hidden = desktop.read_text()
    run(desktop, "hide")
    assert desktop.read_text() == hidden
    assert hidden.count("NoDisplay=true") == 1

    run(desktop, "show")
    run(desktop, "show")
    assert desktop.read_text() == DESKTOP


def test_upstream_nodisplay_is_left_untouched(desktop):
    upstream = DESKTOP.replace("Type=Application\n", "Type=Application\nNoDisplay=true\n")
    desktop.write_text(upstream)
    run(desktop, "hide")
    run(desktop, "show")
    assert desktop.read_text() == upstream


def test_missing_desktop_file_is_ignored(tmp_path):
    run(tmp_path / "absent.desktop", "hide")
    run(tmp_path / "absent.desktop", "show")
    assert not (tmp_path / "absent.desktop").exists()


def test_hooks_cover_gnome_shell_updates_and_package_removal():
    hide = (HOOKS / "big-gnome-center-hide-extensions-app.hook").read_text()
    show = (HOOKS / "big-gnome-center-show-extensions-app.hook").read_text()
    target = "Target = usr/share/libalpm/scripts/big-gnome-center-extensions-app"

    assert "Target = usr/share/applications/org.gnome.Extensions.desktop" in hide
    assert target in hide and "Operation = Upgrade" in hide
    assert hide.rstrip().endswith("big-gnome-center-extensions-app hide")
    assert target in show and "Operation = Remove" in show
    assert "When = PreTransaction" in show
    assert show.rstrip().endswith("big-gnome-center-extensions-app show")
    assert os.access(SCRIPT, os.X_OK)
