# SPDX-License-Identifier: MIT
"""XDG paths, executable checks and lossless autostart overrides."""

import runpy
from pathlib import Path

import pytest
from gi.repository import GLib

import constants
from startup_manager import StartupManager


@pytest.mark.parametrize(
    "configured", [None, "", "relative", "~/config", "/custom/config", "/custom/trailing "]
)
def test_config_home_requires_absolute_path(configured, monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    if configured is None:
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    else:
        monkeypatch.setenv("XDG_CONFIG_HOME", configured)
    expected = (
        Path(configured) if configured and configured.startswith("/") else tmp_path / ".config"
    )
    assert StartupManager().user_dir == expected / "autostart"


@pytest.mark.parametrize(
    ("configured", "expected"),
    [(None, ["/etc/xdg"]), ("", ["/etc/xdg"]), ("relative", []),
     ("~/config", []), (":/one:relative:/two::", ["/one", "/two"]),
     ("/one:/one:/two", ["/one", "/two"]), ("/trailing ", ["/trailing "])],
)
def test_config_dirs_defaults_and_precedence(configured, expected, monkeypatch):
    if configured is None:
        monkeypatch.delenv("XDG_CONFIG_DIRS", raising=False)
    else:
        monkeypatch.setenv("XDG_CONFIG_DIRS", configured)
    assert StartupManager().system_dirs == [Path(value) / "autostart" for value in expected]


@pytest.mark.parametrize(
    "kind", ["executable", "nonexecutable", "directory", "missing", "symlink", "broken"]
)
@pytest.mark.parametrize("absolute", [True, False])
def test_tryexec_requires_executable_file(kind, absolute, tmp_path, monkeypatch):
    program = tmp_path / "test-program"
    if kind in {"executable", "nonexecutable"}:
        program.write_text("#!/bin/sh\nexit 0\n")
        program.chmod(0o755 if kind == "executable" else 0o644)
    elif kind == "directory":
        program.mkdir()
    elif kind in {"symlink", "broken"}:
        program.symlink_to("/usr/bin/true" if kind == "symlink" else tmp_path / "absent")
    monkeypatch.setenv("PATH", str(tmp_path))
    value = str(program) if absolute else program.name
    assert StartupManager._is_visible({"TryExec": value}) is (kind in {"executable", "symlink"})


def test_tryexec_decodes_filename_without_shell_expansion(tmp_path, monkeypatch):
    program = tmp_path / "program with space"
    program.write_text("#!/bin/sh\nexit 0\n")
    program.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert StartupManager._is_visible({"TryExec": str(program).replace(" ", r"\s")})
    assert StartupManager._is_visible({"TryExec": r"program\swith\sspace"})
    assert not StartupManager._is_visible({"TryExec": str(program) + " --argument"})
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert not StartupManager._is_visible({"TryExec": "~/program with space"})


@pytest.mark.parametrize(
    "name", ["Normal", "Português", r"Literal\nText", "Line\nHidden=false\n[Injected]",
             "Tab\tReturn\r", " leading and trailing "]
)
def test_hidden_override_roundtrips_name_with_glib(name, tmp_path, monkeypatch):
    monkeypatch.setenv("LANGUAGE", "pt_BR")
    system = tmp_path / "system"
    system.mkdir()
    source = system / "example.desktop"
    keyfile = GLib.KeyFile()
    keyfile.set_string("Desktop Entry", "Type", "Application")
    keyfile.set_string("Desktop Entry", "Name", "Original")
    keyfile.set_string("Desktop Entry", "Name[pt_BR]", name)
    if name.startswith(" "):
        keyfile.set_value("Desktop Entry", "Name[pt_BR]", name.replace(" ", r"\s"))
    keyfile.set_string("Desktop Entry", "Exec", "/usr/bin/true")
    source.write_text(keyfile.to_data()[0])
    original = source.read_bytes()
    manager = StartupManager(tmp_path / "user", [system])
    assert manager.add_application(source) == (True, "")
    assert manager.list_entries()[0].name == name
    assert manager.remove(source.name) == (True, "")
    result = GLib.KeyFile()
    result.load_from_file(str(manager.user_dir / source.name), GLib.KeyFileFlags.NONE)
    assert result.get_string("Desktop Entry", "Name") == name
    assert result.get_boolean("Desktop Entry", "Hidden")
    assert list(result.get_groups()[0]) == ["Desktop Entry"]
    assert source.read_bytes() == original
    assert manager.list_entries() == []


def test_failed_override_preserves_user_and_system_files(tmp_path, monkeypatch):
    system = tmp_path / "system"
    system.mkdir()
    source = system / "example.desktop"
    source.write_text("[Desktop Entry]\nType=Application\nName=Example\nExec=true\n")
    manager = StartupManager(tmp_path / "user", [system])
    assert manager.add_application(source) == (True, "")
    original = source.read_bytes()

    def fail_replace(*args):
        raise OSError("injected publication failure")

    monkeypatch.setattr("startup_manager.os.replace", fail_replace)
    assert manager.remove(source.name) == (False, "injected publication failure")
    assert (manager.user_dir / source.name).read_bytes() == original
    assert source.read_bytes() == original
    assert list(manager.user_dir.iterdir()) == [manager.user_dir / source.name]


@pytest.mark.parametrize(
    "configured", [None, "", "relative", "~/data", "/custom/data", "/custom/trailing "]
)
def test_extension_directory_uses_xdg_data_home(configured, tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    if configured is None:
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    else:
        monkeypatch.setenv("XDG_DATA_HOME", configured)
    values = runpy.run_path(constants.__file__)
    expected = (
        Path(configured) if configured and configured.startswith("/") else tmp_path / ".local/share"
    )
    assert values["EXT_USER_DIR"] == expected / "gnome-shell/extensions"
    assert values["EXT_SYS_DIR"] == Path("/usr/share/gnome-shell/extensions")
    assert list(tmp_path.iterdir()) == []


def test_default_manager_uses_xdg_override_and_preserves_precedence(tmp_path, monkeypatch):
    user = tmp_path / "config with spaces"
    first = tmp_path / "first" / "autostart"
    second = tmp_path / "second" / "autostart"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(user))
    monkeypatch.setenv("XDG_CONFIG_DIRS", f"relative:{first.parent}:{second.parent}")
    originals = {}
    for directory, name in [(first, "First"), (second, "Second")]:
        directory.mkdir(parents=True)
        source = directory / "example.desktop"
        source.write_text(f"[Desktop Entry]\nType=Application\nName={name}\nExec=true\n")
        originals[source] = source.read_bytes()
    manager = StartupManager()
    assert manager._system_entry("example.desktop") == first / "example.desktop"
    assert manager.add_application(second / "example.desktop") == (True, "")
    assert manager.list_entries()[0].name == "Second"
    assert manager.remove("example.desktop") == (True, "")
    result = GLib.KeyFile()
    result.load_from_file(str(user / "autostart/example.desktop"), GLib.KeyFileFlags.NONE)
    assert result.get_string("Desktop Entry", "Name") == "Second"
    assert result.get_boolean("Desktop Entry", "Hidden")
    assert manager.list_entries() == []
    for source, content in originals.items():
        assert source.read_bytes() == content


def test_icon_path_decodes_escapes_once(tmp_path):
    source = tmp_path / "example.desktop"
    source.write_text(
        "[Desktop Entry]\nType=Application\nName=Example\nExec=true\n"
        r"Icon=/icons/with\sspace/literal\\name.svg" + "\n"
    )
    assert StartupManager(tmp_path, []).list_entries()[0].icon == (
        r"/icons/with space/literal\name.svg"
    )
