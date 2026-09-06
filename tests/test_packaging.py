# SPDX-License-Identifier: MIT
"""Validate the staged package, including legacy upgrade paths."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_package_preserves_legacy_directories(tmp_path):
    for command in ("bash", "glib-compile-schemas", "msgfmt", "realpath"):
        if shutil.which(command) is None:
            pytest.skip(f"{command} is required for package validation")
    source = tmp_path / "src"
    source.mkdir()
    payload = source / "big-gnome-center"
    shutil.copytree(ROOT / "usr", payload / "usr", symlinks=True)
    cache = payload / "usr/share/big-gnome-center/__pycache__"
    cache.mkdir(exist_ok=True)
    (cache / "stale.cpython-314.pyc").write_bytes(b"stale bytecode")
    package = tmp_path / "pkg"
    package.mkdir()
    subprocess.run(
        [
            "bash", "-c",
            'set -e; source "$1"; srcdir="$2"; pkgdir="$3"; package',
            "package-test", str(ROOT / "pkgbuild/PKGBUILD"), str(source), str(package),
        ],
        check=True, capture_output=True, text=True,
    )
    primary = package / "usr/share/big-gnome-center"
    policy = Path("usr/share/polkit-1/actions/br.com.biglinux.BigGnomeCenter.policy")
    assert (package / policy).read_bytes() == (ROOT / policy).read_bytes()
    assert (package / policy).stat().st_mode & 0o022 == 0
    gtk_follower = Path(
        "usr/share/gnome-shell/extensions/layout-switcher-helper@communitybig.org/gtkTheme.js"
    )
    assert (package / gtk_follower).read_bytes() == (ROOT / gtk_follower).read_bytes()
    legacy = package / "usr/share/layout-switcher"
    assert not list(package.rglob("*.pyc"))
    assert not list(package.rglob("*.pyo"))
    for directory in (legacy, legacy / "ui", legacy / "layouts", legacy / "effects"):
        assert directory.is_dir()
        assert not directory.is_symlink()
    files = [path for path in primary.rglob("*") if path.is_file()]
    assert files
    for path in files:
        alias = legacy / path.relative_to(primary)
        assert alias.is_symlink()
        assert not alias.readlink().is_absolute()
        assert alias.resolve() == path.resolve()
    assert (package / "usr/bin/layout-switcher").resolve() == package / "usr/bin/big-gnome-center"
