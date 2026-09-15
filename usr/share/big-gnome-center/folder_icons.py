# SPDX-License-Identifier: MIT
"""Papient folder choices and native Nautilus metadata."""

from dataclasses import dataclass
from pathlib import Path

from gi.repository import Gio

from constants import tr
from folder_accent import _HIGHLIGHT, BASES, base_theme, icon_roots

CUSTOM_URI = "metadata::custom-icon"
CUSTOM_NAME = "metadata::custom-icon-name"
ATTRIBUTES = (CUSTOM_URI, CUSTOM_NAME)

LABELS = {
    "folder": tr("Folder"),
    "applications": tr("Applications"),
    "backup": tr("Backup"),
    "bookmark": tr("Bookmark"),
    "bookmarks": tr("Bookmarks"),
    "books": tr("Books"),
    "camera": tr("Camera"),
    "cloud": tr("Cloud"),
    "comic": tr("Comics"),
    "decrypted": tr("Decrypted"),
    "desktop": tr("Desktop"),
    "development": tr("Development"),
    "documents": tr("Documents"),
    "download": tr("Downloads"),
    "downloads": tr("Downloads"),
    "encrypted": tr("Encrypted"),
    "favorites": tr("Favorites"),
    "games": tr("Games"),
    "home": tr("Home"),
    "home2": tr("Home"),
    "image-people": tr("People"),
    "image": tr("Pictures"),
    "images": tr("Pictures"),
    "important": tr("Important"),
    "locked": tr("Locked"),
    "mail-cloud": tr("Cloud Mail"),
    "mail": tr("Mail"),
    "man": tr("Manuals"),
    "music": tr("Music"),
    "network": tr("Network"),
    "notes": tr("Notes"),
    "paleorange": tr("Alternate Folder"),
    "photo": tr("Photo"),
    "photos": tr("Photos"),
    "picture": tr("Pictures"),
    "pictures": tr("Pictures"),
    "print": tr("Printing"),
    "private": tr("Private"),
    "projects": tr("Projects"),
    "public": tr("Public"),
    "publicshare": tr("Public"),
    "recent": tr("Recent"),
    "remote": tr("Remote"),
    "script": tr("Scripts"),
    "sound": tr("Music"),
    "sync": tr("Synchronization"),
    "tar": tr("Archives"),
    "temp": tr("Temporary"),
    "templates": tr("Templates"),
    "text": tr("Text"),
    "txt": tr("Text"),
    "unlocked": tr("Unlocked"),
    "video": tr("Videos"),
    "videocamera": tr("Video Camera"),
    "videos": tr("Videos"),
    "visiting": tr("Visiting"),
    "wordprocessing": tr("Word Processing"),
}
BRANDS = {
    "android": "Android",
    "apple": "Apple",
    "arduino": "Arduino",
    "cd": "CD",
    "docker": "Docker",
    "dropbox": "Dropbox",
    "gdrive": "Google Drive",
    "git": "Git",
    "github": "GitHub",
    "gitlab": "GitLab",
    "gnome": "GNOME",
    "google-drive": "Google Drive",
    "html": "HTML",
    "java": "Java",
    "kde": "KDE",
    "linux": "Linux",
    "mega": "MEGA",
    "meocloud": "MEO Cloud",
    "nextcloud": "Nextcloud",
    "obsidian": "Obsidian",
    "onedrive": "OneDrive",
    "owncloud": "ownCloud",
    "pcloud": "pCloud",
    "snap": "Snap",
    "steam": "Steam",
    "systemd": "systemd",
    "torrent": "BitTorrent",
    "vbox": "VirtualBox",
    "vmware": "VMware",
    "wifi": "Wi-Fi",
    "yandex-disk": "Yandex Disk",
}


@dataclass(frozen=True)
class FolderIcon:
    name: str
    label: str
    source: Path
    aliases: tuple[str, ...]


def available_icons(theme: str, roots: list[Path] | None = None) -> list[FolderIcon]:
    """List scalable accent-aware artwork; collapse symlink aliases."""
    base = base_theme(theme)
    if base not in BASES:
        return []
    by_source: dict[Path, list[str]] = {}
    seen = set()
    for root in icon_roots() if roots is None else roots:
        places = root / base / "scalable/places"
        for path in sorted(places.glob("folder*.svg")):
            name = path.stem
            if name in seen:
                continue
            seen.add(name)
            if name.endswith(("-open", "_open", "-drag-accept", "-symbolic")):
                continue
            try:
                if path.stat().st_size > 1024 * 1024:
                    continue
                if not _HIGHLIGHT.search(path.read_text()):
                    continue
                by_source.setdefault(path.resolve(), []).append(name)
            except (OSError, UnicodeError, RuntimeError):
                continue
    choices = []
    for source, names in by_source.items():
        name = source.stem if source.stem in names else names[0]
        key = name.removeprefix("folder-").removeprefix("folder_")
        label = LABELS.get(key, BRANDS.get(key, key.replace("-", " ").title()))
        choices.append(FolderIcon(name, label, source, tuple(names)))
    return sorted(choices, key=lambda icon: (icon.name != "folder", icon.label.casefold()))


def read_metadata(folder: Gio.File) -> dict[str, str | None]:
    if not folder.is_native():
        raise ValueError(tr("Choose a local folder."))
    info = folder.query_info(
        "standard::type," + ",".join(ATTRIBUTES), Gio.FileQueryInfoFlags.NONE, None
    )
    if info.get_file_type() != Gio.FileType.DIRECTORY:
        raise ValueError(tr("Choose a local folder."))
    return {key: info.get_attribute_string(key) for key in ATTRIBUTES}


def selected_icon(
    metadata: dict[str, str | None],
    choices: list[FolderIcon],
    roots: list[Path] | None = None,
) -> str | None:
    """Recognize theme files only; personal images are never matched by basename."""
    uri = metadata[CUSTOM_URI]
    if not uri:
        return next((icon.name for icon in choices if metadata[CUSTOM_NAME] in icon.aliases), None)
    path_string = Gio.File.new_for_uri(uri).get_path()
    if not path_string:
        return None
    path = Path(path_string)
    roots = icon_roots() if roots is None else roots
    for root in roots:
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if len(relative.parts) < 2 or base_theme(relative.parts[0]) not in BASES:
            continue
        # Match the same basename only within a recognized installed theme.
        if ".." in relative.parts:
            continue
        try:
            source = path.resolve(strict=True)
            for icon in choices:
                if source == icon.source or path.stem in icon.aliases:
                    return icon.name
        except (OSError, RuntimeError):
            continue
    return None


def _write_attribute(folder: Gio.File, key: str, value: str | None) -> None:
    if value is None:
        success = folder.set_attribute(
            key, Gio.FileAttributeType.INVALID, None, Gio.FileQueryInfoFlags.NONE, None
        )
    else:
        success = folder.set_attribute_string(key, value, Gio.FileQueryInfoFlags.NONE, None)
    if not success:
        raise OSError(tr("Could not save the folder icon."))


def save_icon(folder: Gio.File, name: str | None, expected: dict[str, str | None]) -> None:
    """Keep original metadata on failure; reject stale dialogs."""
    previous = read_metadata(folder)
    if previous != expected:
        raise ValueError(tr("The folder icon changed. Close this window and try again."))
    changes = ((CUSTOM_NAME, name), (CUSTOM_URI, None))
    applied = []
    try:
        for key, value in changes:
            if previous[key] != value:
                _write_attribute(folder, key, value)
                applied.append(key)
    except Exception as error:
        try:
            for key in reversed(applied):
                _write_attribute(folder, key, previous[key])
        except Exception as rollback_error:
            raise OSError(tr("Could not restore the previous folder icon.")) from rollback_error
        raise error
