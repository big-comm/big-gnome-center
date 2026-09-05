# SPDX-License-Identifier: MIT
"""Tests for the privileged system extension removal helper."""

import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import system_extension_remover
from system_extension_remover import extension_target, remove_extension

ROOT = Path(__file__).resolve().parents[1]


def test_extension_target_accepts_uuid(tmp_path):
    assert extension_target("example@test.org", tmp_path) == tmp_path / "example@test.org"


@pytest.mark.parametrize(
    "uuid",
    ["", ".", "..", "../example@test.org", "nested/example@test.org", "-option"],
)
def test_extension_target_rejects_unsafe_uuid(tmp_path, uuid):
    with pytest.raises(ValueError, match="invalid extension UUID"):
        extension_target(uuid, tmp_path)


def test_remove_extension_deletes_only_selected_directory(tmp_path):
    selected = tmp_path / "selected@test.org"
    untouched = tmp_path / "untouched@test.org"
    selected.mkdir()
    untouched.mkdir()
    (selected / "metadata.json").write_text("{}")

    remove_extension("selected@test.org", tmp_path)

    assert not selected.exists()
    assert untouched.is_dir()


def test_remove_extension_unlinks_symlink_without_following_it(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "linked@test.org"
    link.symlink_to(outside, target_is_directory=True)

    remove_extension("linked@test.org", tmp_path)

    assert not link.exists()
    assert outside.is_dir()


def test_privileged_launcher_is_packaged_and_executable():
    launcher = ROOT / "usr/bin/big-gnome-center-remove-extension"

    assert launcher.is_file()
    assert os.access(launcher, os.X_OK)


def test_removal_policy_retains_only_active_admin_authorization():
    policy = ET.parse(ROOT / "usr/share/polkit-1/actions/br.com.biglinux.BigGnomeCenter.policy")
    actions = policy.getroot().findall("action")
    assert len(actions) == 1
    action = actions[0]
    assert action.get("id") == "br.com.biglinux.BigGnomeCenter.remove-system-extension"
    assert {entry.tag: entry.text for entry in action.find("defaults")} == {
        "allow_any": "auth_admin",
        "allow_inactive": "auth_admin",
        "allow_active": "auth_admin_keep",
    }
    assert {entry.get("key"): entry.text for entry in action.findall("annotate")} == {
        "org.freedesktop.policykit.exec.path": "/usr/bin/big-gnome-center-remove-extension",
    }
    for tag in ("description", "message"):
        assert action.findtext(tag)
        assert action.findtext(f"{tag}[@{{http://www.w3.org/XML/1998/namespace}}lang='pt_BR']")


@pytest.mark.parametrize("args", [[], ["first@test.org", "second@test.org"]])
def test_privileged_helper_requires_exactly_one_uuid(monkeypatch, args):
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        system_extension_remover, "remove_extension", lambda uuid: pytest.fail(uuid),
    )
    assert system_extension_remover.main(args) == 64


def test_privileged_helper_requires_root(monkeypatch):
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    monkeypatch.setattr(
        system_extension_remover, "remove_extension", lambda uuid: pytest.fail(uuid),
    )
    assert system_extension_remover.main(["example@test.org"]) == 77


def test_package_declares_polkit_runtime_dependency():
    pkgbuild = (ROOT / "pkgbuild/PKGBUILD").read_text(encoding="utf-8")

    assert "'polkit'" in pkgbuild


def test_package_replaces_previous_layout_switcher_names():
    pkgbuild = (ROOT / "pkgbuild/PKGBUILD").read_text(encoding="utf-8")

    assert "pkgname=big-gnome-center" in pkgbuild
    assert "conflicts=('layout-switcher' 'gnome-layout-switcher')" in pkgbuild
    assert "provides=('layout-switcher' 'gnome-layout-switcher')" in pkgbuild
    assert "replaces=('layout-switcher' 'gnome-layout-switcher')" in pkgbuild
