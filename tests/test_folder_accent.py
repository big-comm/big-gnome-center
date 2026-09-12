# SPDX-License-Identifier: MIT
"""Folder overlays and async follower; no host desktop settings."""

import configparser
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from constants import ACCENT_COLORS
from folder_accent import BASES, base_theme, build_theme
from layout_applier import LayoutApplier
from theme_manager import ThemeMgr

ROOT = Path(__file__).resolve().parents[1]
MODULE = (
    ROOT
    / "usr/share/gnome-shell/extensions/layout-switcher-helper@communitybig.org/folderAccent.js"
)
SCRIPT = ROOT / "usr/share/big-gnome-center/folder_accent.py"
SVG = '<svg><style>.ColorScheme-Highlight {color:#3584e4;}</style><path fill="#123456"/></svg>'


@pytest.fixture
def icons(tmp_path):
    root = tmp_path / "system/icons"
    for base in BASES:
        theme = root / base
        places = theme / "scalable/places"
        places.mkdir(parents=True)
        (theme / "index.theme").write_text(
            "[Icon Theme]\nName=Test\nDirectories=scalable/places\n"
            "[scalable/places]\nContext=Places\nSize=48\nType=Scalable\nMinSize=28\nMaxSize=512\n"
        )
        (places / "folder.svg").write_text(SVG)
        (places / "folder-documents.svg").symlink_to("folder.svg")
        (places / "user-home.svg").symlink_to("folder.svg")
        (places / "folder-red.svg").write_text('<svg fill="#ff0000"/>')
        (places / "drive.svg").write_text(SVG)
    return root


@pytest.mark.parametrize("base", BASES)
@pytest.mark.parametrize("accent", ACCENT_COLORS)
def test_palette_and_source_preservation(tmp_path, icons, base, accent):
    output = tmp_path / "user/icons"
    result = build_theme(base, accent, [icons], output)
    assert (icons / base / "scalable/places/folder.svg").read_text() == SVG
    assert base_theme(result["theme"]) == base
    if accent == "blue":
        assert result["theme"] == base
        assert not output.exists()
        return
    theme = output / result["theme"]
    assert result["icons"] == 3
    for name in ("folder.svg", "folder-documents.svg", "user-home.svg"):
        data = (theme / "scalable/places" / name).read_text()
        assert ACCENT_COLORS[accent] in data
        assert "#123456" in data
        assert not (theme / "scalable/places" / name).is_symlink()
    assert not (theme / "scalable/places/drive.svg").exists()
    assert not (theme / "scalable/places/folder-red.svg").exists()
    cfg = configparser.ConfigParser()
    cfg.read(theme / "index.theme")
    assert cfg["Icon Theme"]["Inherits"] == base
    assert cfg["Icon Theme"]["Hidden"] == "true"
    assert cfg["scalable/places"]["MinSize"] == "28"
    assert build_theme(result["theme"], accent, [icons], output) == result
    assert build_theme(result["theme"], "blue", [icons], output)["theme"] == base


def test_content_updates_and_collision(tmp_path, icons):
    output = tmp_path / "output"
    first = build_theme(BASES[0], "red", [icons], output)
    icon = icons / BASES[0] / "scalable/places/folder.svg"
    icon.write_text(SVG.replace("#123456", "#654321"))
    second = build_theme(first["theme"], "red", [icons], output)
    assert first["theme"] != second["theme"]
    (output / second["theme"] / "scalable/places/folder.svg").write_text("User edit")
    with pytest.raises(ValueError, match="collision"):
        build_theme(second["theme"], "red", [icons], output)


def test_custom_missing_and_unsupported(tmp_path, icons):
    output = tmp_path / "output"
    assert build_theme("Custom", "red", [icons], output)["theme"] == "Custom"
    assert build_theme(BASES[0], "../bad", [icons], output)["status"] == "unsupported"
    assert base_theme("bgc-folders--../Custom--red--0123456789abcdef") != "Custom"
    with pytest.raises(ValueError, match="Missing"):
        build_theme(BASES[0], "red", [], output)
    folder = icons / BASES[0] / "scalable/places/folder.svg"
    folder.write_text("<svg/>")
    assert build_theme(BASES[0], "red", [icons], output)["status"] == "unavailable"
    assert not output.exists()


def test_overlay_is_presented_as_base(tmp_path, icons, monkeypatch):
    output = tmp_path / "output"
    result = build_theme(BASES[0], "green", [icons], output)
    monkeypatch.setattr("theme_manager.gsettings_get", lambda *args: result["theme"])
    monkeypatch.setattr(ThemeMgr, "_theme_roots", lambda kind: [output])
    assert ThemeMgr.current("icons") == BASES[0]
    assert ThemeMgr.list_themes("icons") == []
    text = ("[org/gnome/desktop/interface]\n"
            f"icon-theme='{result['theme']}'\ncolor-scheme='prefer-dark'\n")
    adjusted = LayoutApplier._adjust_icon_theme_for_scheme(text)
    assert "icon-theme='bigicons-papient-dark'" in adjusted


def test_native_follower(tmp_path, icons):
    if not shutil.which("gjs"):
        pytest.skip("gjs required")
    script = tmp_path / "check.mjs"
    script.write_text(
        f"import {{FolderAccentFollower, folderBaseTheme}} from '{MODULE.as_uri()}';\n"
        + f"const script = {str(SCRIPT)!r};\n"
        + r"""
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
function equal(a, b) { if (a !== b) throw new Error(`${a} != ${b}`); }
function wait() {
    const loop = new GLib.MainLoop(null, false);
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1100, () => {loop.quit(); return GLib.SOURCE_REMOVE;});
    loop.run();
}
const settings = new Gio.Settings({schema_id: 'org.gnome.desktop.interface'});
settings.set_string('icon-theme', 'bigicons-papient');
settings.set_string('accent-color', 'purple');
let busy = true;
const follower = new FolderAccentFollower(settings, () => busy, error => {throw error;}, script);
wait();
equal(settings.get_string('icon-theme'), 'bigicons-papient');
busy = false;
wait();
equal(follower.diagnostics().status, 'ready');
equal(folderBaseTheme(settings.get_string('icon-theme')), 'bigicons-papient');
equal(settings.get_string('icon-theme').includes('--purple--'), true);
settings.set_string('accent-color', 'orange');
settings.set_string('accent-color', 'green');
settings.set_string('icon-theme', 'bigicons-papient-dark');
wait();
equal(settings.get_string('icon-theme').includes('--bigicons-papient-dark--green--'), true);
settings.set_string('accent-color', 'blue');
wait();
equal(settings.get_string('icon-theme'), 'bigicons-papient-dark');
settings.set_string('icon-theme', 'Custom');
settings.set_string('accent-color', 'red');
wait();
equal(settings.get_string('icon-theme'), 'Custom');
equal(follower.diagnostics().status, 'unsupported');
settings.set_string('icon-theme', 'bigicons-papient');
follower.destroy();
wait();
equal(settings.get_string('icon-theme'), 'bigicons-papient');
"""
    )
    env = {
        **os.environ,
        "GSETTINGS_BACKEND": "memory",
        "HOME": str(tmp_path),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "XDG_DATA_DIRS": f"{icons.parent}:/usr/share",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    result = subprocess.run(
        ["gjs", "-m", str(script)], env=env, capture_output=True, text=True, timeout=20
    )
    assert result.returncode == 0, result.stdout + result.stderr
