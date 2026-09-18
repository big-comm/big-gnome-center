# SPDX-License-Identifier: MIT
"""Subprocess channel isolation and serialized settings contracts."""

import logging
import os
import shutil
import subprocess
import sys
from unittest.mock import patch

import pytest
from gi.repository import GLib

import backup_manager
import snapshot_manager
from utils import dconf_read, gsettings_get, gsettings_set, run_cmd


@pytest.mark.parametrize("stdout", ["", "payload\n"])
def test_success_returns_stdout_only(stdout, caplog):
    with caplog.at_level(logging.DEBUG, logger="big-gnome-center"):
        result = run_cmd([
            sys.executable, "-c",
            f"import sys; sys.stdout.write({stdout!r}); sys.stderr.write('diagnostic')",
        ])
    assert result == (True, stdout.strip())
    assert "diagnostic" in caplog.text


@pytest.mark.parametrize("stderr,expected", [("error", "error"), ("", "output")])
def test_failure_returns_diagnostics(stderr, expected):
    assert run_cmd([
        sys.executable, "-c",
        f"import sys; print('output'); sys.stderr.write({stderr!r}); sys.exit(7)",
    ]) == (False, expected)


STRINGS = ["", "  spaced  ", "'quoted'", '"quoted"', "C:\\themes\\new",
           "line\nnext\tcolumn", "ação 日本語"]


@pytest.mark.parametrize("value", STRINGS)
def test_gsettings_decodes_strings(value):
    serialized = GLib.Variant("s", value).print_(True)
    with patch("utils.run_cmd", return_value=(True, serialized)):
        assert gsettings_get("test.schema", "text") == value


def test_gsettings_decodes_annotated_string():
    with patch("utils.run_cmd", return_value=(True, "@s '  text  '")):
        assert gsettings_get("test.schema", "text") == "  text  "


@pytest.mark.parametrize("serialized", ["true", "false", "1.25", "uint32 4",
                                       "['one', 'two']", "@as []"])
def test_gsettings_preserves_nonstring_serialization(serialized):
    with patch("utils.run_cmd", return_value=(True, serialized)):
        assert gsettings_get("test.schema", "value") == serialized


@pytest.mark.parametrize("serialized", ["", "warning: backend unavailable", "'unfinished"])
def test_gsettings_rejects_invalid_serialization(serialized):
    with patch("utils.run_cmd", return_value=(True, serialized)):
        assert gsettings_get("test.schema", "text") is None


@pytest.mark.parametrize("has_data", [False, True])
def test_dump_diagnostics_never_replace_saved_data(tmp_path, monkeypatch, has_data):
    """Exercise real subprocesses and both persistence consumers."""
    payload = "[org/gnome/desktop/interface]\nfont-name='" + "x" * 120 + "'\n"
    diagnostic = "warning: " + "backend diagnostic " * 12
    bindir = tmp_path / "bin"
    bindir.mkdir()
    command = bindir / "dconf"
    command.write_text(
        f"#!{sys.executable}\nimport sys\n"
        f"sys.stdout.write({payload if has_data else ''!r})\n"
        f"sys.stderr.write({diagnostic!r})\n"
    )
    command.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])
    backups = tmp_path / "backups"
    backups.mkdir()
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    monkeypatch.setattr(backup_manager, "BACKUP_DIR", backups)
    monkeypatch.setattr(snapshot_manager, "SNAPSHOTS_DIR", snapshots)
    previous = backups / "backup_previous.dconf"
    previous.write_text(payload)
    latest = backups / "latest.dconf"
    latest.symlink_to(previous.name)
    snapshot = snapshots / "deskux.dconf"
    snapshot.write_text(payload)

    assert backup_manager.BackupManager.create()[0] is has_data
    assert snapshot_manager.SnapshotManager.save("deskux")[0] is has_data
    assert previous.read_text() == payload
    assert snapshot.read_text() == (payload.strip() if has_data else payload)
    assert dconf_read("/test/value") == (payload.strip() if has_data else None)
    if has_data:
        assert latest.read_text() == payload.strip()
    else:
        assert latest.readlink().name == previous.name
        assert sorted(p.name for p in backups.iterdir()) == [previous.name, latest.name]


@pytest.fixture
def isolated_gsettings(tmp_path, monkeypatch):
    for command in ("gsettings", "glib-compile-schemas"):
        if not shutil.which(command):
            pytest.skip(f"Requires {command}")
    schema = "org.bigcommunity.test.command-contracts"
    (tmp_path / "test.gschema.xml").write_text(
        f'<schemalist><schema id="{schema}" path="/org/bigcommunity/test/">'
        '<key name="text" type="s"><default>\'\'</default></key>'
        '<key name="enabled" type="b"><default>false</default></key>'
        '<key name="scale" type="d"><default>1.0</default></key>'
        '<key name="apps" type="as"><default>[]</default></key>'
        '<key name="count" type="u"><default>0</default></key>'
        '</schema></schemalist>'
    )
    subprocess.run(["glib-compile-schemas", "--strict", str(tmp_path)], check=True)
    monkeypatch.setenv("GSETTINGS_SCHEMA_DIR", str(tmp_path))
    monkeypatch.setenv("GSETTINGS_BACKEND", "keyfile")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    return schema


@pytest.mark.parametrize("value", STRINGS)
def test_native_gsettings_string_roundtrip(isolated_gsettings, value):
    assert gsettings_set(isolated_gsettings, "text", GLib.Variant("s", value).print_(True))[0]
    assert gsettings_get(isolated_gsettings, "text") == value


@pytest.mark.parametrize("key,signature,value", [
    ("enabled", "b", True), ("scale", "d", 1.25),
    ("apps", "as", ["one.desktop", "two.desktop"]), ("apps", "as", []),
    ("count", "u", 4),
])
def test_native_gsettings_nonstring_contract(isolated_gsettings, key, signature, value):
    assert gsettings_set(isolated_gsettings, key, GLib.Variant(signature, value).print_(True))[0]
    output = gsettings_get(isolated_gsettings, key)
    assert isinstance(output, str)
    parsed = GLib.Variant.parse(GLib.VariantType(signature), output, None, None)
    assert parsed.unpack() == value
