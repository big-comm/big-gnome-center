# SPDX-License-Identifier: MIT
"""Tests for XDG startup application management."""

from pathlib import Path
from unittest.mock import patch

from startup_manager import StartupManager


def _desktop(path: Path, name: str, extra: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"[Desktop Entry]\nType=Application\nName={name}\nExec=/usr/bin/true\n{extra}",
        encoding="utf-8",
    )
    return path


class _FakeApp:
    def __init__(self, path: Path, name: str, visible: bool = True) -> None:
        self._path = path
        self._name = name
        self._visible = visible

    def get_filename(self):
        return str(self._path)

    def should_show(self):
        return self._visible

    def get_icon(self):
        return None

    def get_display_name(self):
        return self._name

    def get_name(self):
        return self._name

    def get_description(self):
        return f"{self._name} description"


def test_lists_effective_entries_with_user_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME:BigLinux")
    user_dir = tmp_path / "user"
    system_dir = tmp_path / "system"
    _desktop(system_dir / "shared.desktop", "System version")
    _desktop(user_dir / "shared.desktop", "User version")
    _desktop(system_dir / "visible.desktop", "Visible", "OnlyShowIn=GNOME;\n")
    _desktop(system_dir / "hidden.desktop", "Hidden", "NoDisplay=true\n")
    _desktop(system_dir / "disabled.desktop", "Disabled", "Hidden=true\n")
    _desktop(system_dir / "other.desktop", "Other", "OnlyShowIn=KDE;\n")

    entries = StartupManager(user_dir, [system_dir]).list_entries()

    assert [entry.name for entry in entries] == ["User version"]
    assert entries[0].user_owned is True


def test_hidden_user_override_masks_system_entry(tmp_path):
    user_dir = tmp_path / "user"
    system_dir = tmp_path / "system"
    _desktop(system_dir / "shared.desktop", "System version")
    _desktop(user_dir / "shared.desktop", "Disabled override", "Hidden=true\n")

    assert StartupManager(user_dir, [system_dir]).list_entries() == []


def test_uses_localized_name_and_description(tmp_path, monkeypatch):
    monkeypatch.setenv("LANGUAGE", "pt_BR:pt")
    user_dir = tmp_path / "user"
    _desktop(
        user_dir / "localized.desktop",
        "English",
        "Name[pt_BR]=Português\nComment=English description\n"
        "Comment[pt_BR]=Descrição em português\n",
    )

    entry = StartupManager(user_dir, []).list_entries()[0]

    assert entry.name == "Português"
    assert entry.description == "Descrição em português"


def test_add_application_copies_desktop_file_atomically(tmp_path):
    source = _desktop(tmp_path / "applications" / "example.desktop", "Example")
    user_dir = tmp_path / "autostart"
    manager = StartupManager(user_dir, [])

    ok, error = manager.add_application(source)

    assert (ok, error) == (True, "")
    assert (user_dir / source.name).read_bytes() == source.read_bytes()
    assert (user_dir / source.name).stat().st_mode & 0o777 == 0o644


def test_lists_visible_applications_and_excludes_existing_ids(tmp_path):
    first = _FakeApp(tmp_path / "apps" / "first.desktop", "First")
    second = _FakeApp(tmp_path / "apps" / "second.desktop", "Second")
    hidden = _FakeApp(tmp_path / "apps" / "hidden.desktop", "Hidden", visible=False)

    with patch("startup_manager.Gio.AppInfo.get_all", return_value=[second, hidden, first]):
        candidates = StartupManager.list_applications({"second.desktop"})

    assert [candidate.desktop_id for candidate in candidates] == ["first.desktop"]
    assert candidates[0].description == "First description"


def test_remove_user_entry_without_system_fallback_deletes_file(tmp_path):
    user_dir = tmp_path / "user"
    path = _desktop(user_dir / "example.desktop", "Example")
    manager = StartupManager(user_dir, [])

    assert manager.remove(path.name) == (True, "")
    assert not path.exists()


def test_remove_system_entry_creates_hidden_user_override(tmp_path):
    user_dir = tmp_path / "user"
    system_dir = tmp_path / "system"
    system_path = _desktop(system_dir / "example.desktop", "Example")
    manager = StartupManager(user_dir, [system_dir])

    assert manager.remove(system_path.name) == (True, "")
    assert system_path.exists()
    assert "Hidden=true" in (user_dir / system_path.name).read_text(encoding="utf-8")
    assert manager.list_entries() == []


def test_remove_user_override_keeps_system_entry_masked(tmp_path):
    user_dir = tmp_path / "user"
    system_dir = tmp_path / "system"
    _desktop(system_dir / "example.desktop", "System")
    _desktop(user_dir / "example.desktop", "Customized")
    manager = StartupManager(user_dir, [system_dir])

    assert manager.remove("example.desktop") == (True, "")
    assert "Hidden=true" in (user_dir / "example.desktop").read_text(encoding="utf-8")
    assert manager.list_entries() == []


def test_rejects_unsafe_desktop_ids(tmp_path):
    manager = StartupManager(tmp_path / "user", [])

    assert manager.remove("../example.desktop")[0] is False
    assert manager.remove("example.txt")[0] is False


def test_window_exposes_startup_navigation():
    root = Path(__file__).resolve().parents[1]
    source = (root / "usr/share/big-gnome-center/ui/window.py").read_text(encoding="utf-8")

    assert "from ui.page_startup import StartupPage" in source
    assert '"startup": lambda: StartupPage' in source
    assert '("startup", tr("Startup Applications"), "folder-symbolic")' in source
    assert '"startup": tr("Startup Applications")' in source
