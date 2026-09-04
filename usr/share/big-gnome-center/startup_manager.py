# SPDX-License-Identifier: MIT
"""Manage XDG autostart entries without modifying package-owned files."""

from __future__ import annotations

import configparser
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio


@dataclass(frozen=True)
class StartupEntry:
    """An effective, user-visible XDG autostart entry."""

    desktop_id: str
    name: str
    description: str
    icon: str
    source: Path
    user_owned: bool


@dataclass(frozen=True)
class ApplicationCandidate:
    """An installed desktop application that can be added to autostart."""

    desktop_id: str
    name: str
    description: str
    icon: str
    source: Path


class StartupManager:
    """Resolve, add, and remove XDG autostart desktop entries."""

    def __init__(
        self,
        user_dir: Optional[Path] = None,
        system_dirs: Optional[Iterable[Path]] = None,
    ) -> None:
        self.user_dir = user_dir if user_dir is not None else self._default_user_dir()
        self.system_dirs = (
            list(system_dirs) if system_dirs is not None else self._default_system_dirs()
        )

    @staticmethod
    def _default_user_dir() -> Path:
        configured = os.environ.get("XDG_CONFIG_HOME", "").strip()
        base = Path(configured).expanduser() if configured else Path.home() / ".config"
        return base / "autostart"

    @staticmethod
    def _default_system_dirs() -> list[Path]:
        configured = os.environ.get("XDG_CONFIG_DIRS", "/etc/xdg")
        return [Path(value).expanduser() / "autostart" for value in configured.split(":") if value]

    @staticmethod
    def _parser(path: Path) -> Optional[configparser.RawConfigParser]:
        parser = configparser.RawConfigParser(
            interpolation=None,
            delimiters=("=",),
            strict=False,
        )
        parser.optionxform = str
        try:
            with path.open("r", encoding="utf-8", errors="replace") as stream:
                parser.read_file(stream)
        except (OSError, configparser.Error):
            return None
        if not parser.has_section("Desktop Entry"):
            return None
        return parser

    @staticmethod
    def _bool_value(section, key: str, default: bool = False) -> bool:
        raw = section.get(key)
        if raw is None:
            return default
        return raw.strip().casefold() in {"1", "true", "yes", "on"}

    @staticmethod
    def _localized_keys(key: str) -> list[str]:
        languages: list[str] = []
        for variable in ("LANGUAGE", "LC_MESSAGES", "LANG"):
            raw = os.environ.get(variable, "")
            for value in raw.split(":"):
                normalized = value.split(".", 1)[0].split("@", 1)[0].strip()
                if normalized and normalized not in {"C", "POSIX"}:
                    languages.append(normalized)
                    if "_" in normalized:
                        languages.append(normalized.split("_", 1)[0])
        return [f"{key}[{language}]" for language in dict.fromkeys(languages)] + [key]

    @classmethod
    def _localized_value(cls, section, key: str) -> str:
        for candidate in cls._localized_keys(key):
            value = section.get(candidate, "").strip()
            if value:
                return value.replace("\\s", " ").replace("\\n", "\n").replace("\\\\", "\\")
        return ""

    @staticmethod
    def _desktop_tokens(value: str) -> set[str]:
        return {token.strip().casefold() for token in value.split(";") if token.strip()}

    @classmethod
    def _is_visible(cls, section) -> bool:
        if section.get("Type", "Application").strip() != "Application":
            return False
        if cls._bool_value(section, "Hidden") or cls._bool_value(section, "NoDisplay"):
            return False
        if not cls._bool_value(section, "X-GNOME-Autostart-enabled", default=True):
            return False

        desktops = {
            item.casefold() for item in os.environ.get("XDG_CURRENT_DESKTOP", "").split(":") if item
        }
        only_show_in = cls._desktop_tokens(section.get("OnlyShowIn", ""))
        not_show_in = cls._desktop_tokens(section.get("NotShowIn", ""))
        if only_show_in and not desktops.intersection(only_show_in):
            return False
        if desktops.intersection(not_show_in):
            return False

        try_exec = section.get("TryExec", "").strip()
        if try_exec:
            executable = Path(try_exec).expanduser()
            if executable.is_absolute():
                if not executable.exists():
                    return False
            elif shutil.which(try_exec) is None:
                return False
        return True

    def _effective_paths(self) -> dict[str, tuple[Path, bool]]:
        effective: dict[str, tuple[Path, bool]] = {}
        for directory, user_owned in [
            (self.user_dir, True),
            *((directory, False) for directory in self.system_dirs),
        ]:
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.desktop")):
                effective.setdefault(path.name, (path, user_owned))
        return effective

    def list_entries(self) -> list[StartupEntry]:
        """Return visible user-managed entries effective in this desktop."""
        entries: list[StartupEntry] = []
        for desktop_id, (path, user_owned) in self._effective_paths().items():
            # Session services from /etc/xdg/autostart are implementation
            # details. Show an entry only after the user has added or
            # explicitly overridden it in their own autostart directory.
            if not user_owned:
                continue
            parser = self._parser(path)
            if parser is None:
                continue
            section = parser["Desktop Entry"]
            if not self._is_visible(section):
                continue
            name = self._localized_value(section, "Name") or path.stem
            description = self._localized_value(section, "Comment")
            entries.append(
                StartupEntry(
                    desktop_id=desktop_id,
                    name=name,
                    description=description,
                    icon=section.get("Icon", "").strip(),
                    source=path,
                    user_owned=user_owned,
                )
            )
        return sorted(entries, key=lambda entry: entry.name.casefold())

    @staticmethod
    def list_applications(excluded_ids: Iterable[str] = ()) -> list[ApplicationCandidate]:
        """Return launchable desktop applications not already in autostart."""
        excluded = set(excluded_ids)
        candidates: dict[str, ApplicationCandidate] = {}
        for app in Gio.AppInfo.get_all():
            get_filename = getattr(app, "get_filename", None)
            filename = get_filename() if get_filename else None
            desktop_id = Path(filename).name if filename else ""
            if (
                not desktop_id
                or desktop_id in excluded
                or not filename
                or not filename.endswith(".desktop")
                or not app.should_show()
            ):
                continue
            icon = app.get_icon()
            candidates.setdefault(
                desktop_id,
                ApplicationCandidate(
                    desktop_id=desktop_id,
                    name=app.get_display_name() or app.get_name() or Path(filename).stem,
                    description=app.get_description() or "",
                    icon=icon.to_string() if icon else "",
                    source=Path(filename),
                ),
            )
        return sorted(candidates.values(), key=lambda app: app.name.casefold())

    @staticmethod
    def _valid_desktop_id(desktop_id: str) -> bool:
        return (
            bool(desktop_id)
            and desktop_id.endswith(".desktop")
            and Path(desktop_id).name == desktop_id
        )

    @staticmethod
    def _atomic_write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.chmod(0o644)
            os.replace(temporary, path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def add_application(self, source: Path) -> tuple[bool, str]:
        """Copy an installed application desktop file into user autostart."""
        desktop_id = source.name
        if not self._valid_desktop_id(desktop_id) or not source.is_file():
            return False, "invalid desktop application"
        parser = self._parser(source)
        if parser is None or parser["Desktop Entry"].get("Type", "Application") != "Application":
            return False, "invalid desktop application"
        try:
            self._atomic_write(self.user_dir / desktop_id, source.read_bytes())
        except OSError as exc:
            return False, str(exc)
        return True, ""

    def _system_entry(self, desktop_id: str) -> Optional[Path]:
        for directory in self.system_dirs:
            candidate = directory / desktop_id
            if candidate.is_file():
                return candidate
        return None

    def remove(self, desktop_id: str) -> tuple[bool, str]:
        """Disable an effective entry, preserving any package-owned source file."""
        if not self._valid_desktop_id(desktop_id):
            return False, "invalid desktop entry"
        user_path = self.user_dir / desktop_id
        system_path = self._system_entry(desktop_id)
        try:
            if system_path is None:
                user_path.unlink(missing_ok=False)
            else:
                parser = self._parser(user_path if user_path.is_file() else system_path)
                name = desktop_id.removesuffix(".desktop")
                if parser is not None:
                    name = self._localized_value(parser["Desktop Entry"], "Name") or name
                override = (
                    f"[Desktop Entry]\nType=Application\nName={name}\nHidden=true\n"
                ).encode("utf-8")
                self._atomic_write(user_path, override)
        except FileNotFoundError:
            return False, "desktop entry not found"
        except OSError as exc:
            return False, str(exc)
        return True, ""
