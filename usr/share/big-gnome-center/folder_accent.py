# SPDX-License-Identifier: MIT
"""User-local Papient folder accents using standard icon-theme inheritance."""

import argparse
import configparser
import ctypes
import errno
import hashlib
import io
import os
import re
import shutil
import stat
import tempfile
from pathlib import Path

from constants import ACCENT_COLORS

BASES = ("bigicons-papient", "bigicons-papient-dark", "bigicons-papient-light")
MAX_FILE_BYTES = 1024 * 1024
PREFIX = "bgc-folders--"
_GENERATED = re.compile(
    r"^bgc-folders--(bigicons-papient(?:-dark|-light)?)--([a-z]+)--[0-9a-f]{16}$"
)
_HIGHLIGHT = re.compile(
    r"(\.ColorScheme-Highlight\s*\{\s*color\s*:\s*)#[0-9a-fA-F]{3,8}(\s*;?\s*\})"
)


def base_theme(name: str) -> str:
    match = _GENERATED.fullmatch(name)
    return match[1] if match and match[2] in ACCENT_COLORS else name


def _data_home() -> Path:
    data = Path(os.environ.get("XDG_DATA_HOME", ""))
    return data if data.is_absolute() else Path.home() / ".local/share"


def icon_roots() -> list[Path]:
    dirs = (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")
    return list(dict.fromkeys([
        Path.home() / ".icons", _data_home() / "icons",
        *[Path(d) / "icons" for d in dirs if Path(d).is_absolute()],
    ]))


def _read_regular(path, limit=MAX_FILE_BYTES, *, dir_fd=None, nofollow=False) -> bytes:
    """Bound reads on the opened file; source theme aliases remain supported."""
    flags = os.O_RDONLY | os.O_NONBLOCK | (os.O_NOFOLLOW if nofollow else 0)
    fd = os.open(path, flags, dir_fd=dir_fd)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError(f"Invalid or oversized icon theme file: {path}")
        data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError(f"Oversized icon theme file: {path}")
        return data


def _verify_overlay(target: Path, files: dict) -> None:
    """Check expected content without following managed directory/file links."""
    try:
        root_fd = os.open(target, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for relative, expected in files.items():
                parent_fd = os.dup(root_fd)
                try:
                    for part in relative.parts[:-1]:
                        child_fd = os.open(
                            part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd
                        )
                        os.close(parent_fd)
                        parent_fd = child_fd
                    actual = _read_regular(
                        relative.name, len(expected), dir_fd=parent_fd, nofollow=True
                    )
                    if actual != expected:
                        raise ValueError("Managed icon theme collision")
                finally:
                    os.close(parent_fd)
        finally:
            os.close(root_fd)
    except (OSError, ValueError) as exc:
        raise ValueError("Managed icon theme collision") from exc


def _publish_directory(source: Path, target: Path) -> None:
    """Atomically publish a complete directory without replacing a winner (Linux)."""
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, "renameat2", None)
    if rename is None:
        raise OSError(errno.ENOSYS, "Atomic icon theme publication is unavailable")
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                       ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(target), 1):
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(target))


def build_theme(current: str, accent: str, roots: list[Path], output: Path) -> dict:
    """Publish an immutable overlay. Never edit the selected source theme."""
    base = base_theme(current)
    result = {"base": base, "accent": accent, "theme": current, "icons": 0}
    if base not in BASES or accent not in ACCENT_COLORS:
        return {**result, "status": "unsupported"}
    # Blue is the upstream artwork; restore the base without an overlay.
    if accent == "blue":
        return {**result, "theme": base, "status": "original"}
    sources = [root / base for root in roots]
    index = next((p / "index.theme" for p in sources if (p / "index.theme").is_file()), None)
    if index is None:
        raise ValueError(f"Missing icon theme: {base}")
    cfg = configparser.ConfigParser(interpolation=None, strict=False)
    cfg.optionxform = str
    cfg.read_string(_read_regular(index).decode("utf-8"))
    candidates = {}
    tinted_names = set()
    sections = {}
    directories = {
        key: [d.strip() for d in cfg.get("Icon Theme", key, fallback="").split(",") if d.strip()]
        for key in ("Directories", "ScaledDirectories")
    }
    for directory in dict.fromkeys(directories["Directories"] + directories["ScaledDirectories"]):
        relative = Path(directory)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Invalid icon directory")
        if cfg.get(directory, "Context", fallback="") not in ("Places", "FileSystems"):
            continue
        if "symbolic" in directory:
            continue
        seen = set()
        for source in sources:
            folder = source / directory
            if not folder.is_dir():
                continue
            for icon in sorted(folder.iterdir()):
                if icon.suffix not in (".svg", ".png", ".xpm") or icon.name in seen:
                    continue
                seen.add(icon.name)
                # user-* also includes trash and bookmarks, which are not folders.
                if not (
                    icon.stem.startswith(("folder", "user-home", "user-desktop"))
                    or icon.stem in ("desktop", "inode-directory")
                ) or icon.stem.endswith("-symbolic"):
                    continue
                data = _read_regular(icon)
                if icon.suffix == ".svg":
                    tinted, count = _HIGHLIGHT.subn(
                        lambda m: m[1] + ACCENT_COLORS[accent] + m[2], data.decode()
                    )
                    if count:
                        data = tinted.encode()
                        tinted_names.add(icon.stem)
                candidates[relative / icon.name] = data
                sections[directory] = dict(cfg[directory])
    # Theme lookup stops at the first theme containing an icon name. Include
    # every size/scale of recolored names, even variants without an accent.
    files = {path: data for path, data in candidates.items() if path.stem in tinted_names}
    if not files:
        # Do not leave an outdated overlay after a source theme loses support.
        return {**result, "theme": base, "status": "unavailable"}
    overlay = configparser.ConfigParser(interpolation=None)
    overlay.optionxform = str
    overlay["Icon Theme"] = {
        "Name": f"{base} ({accent})",
        "Comment": "Big Gnome Center folder accents",
        "Inherits": base,
        "Hidden": "true",
    }
    used = {str(path.parent) for path in files}
    for key, names in directories.items():
        included = list(dict.fromkeys(name for name in names if name in used))
        if included or key == "Directories":
            overlay["Icon Theme"][key] = ",".join(included)
    for name in sections:
        if name in used:
            overlay[name] = sections[name]
    stream = io.StringIO()
    overlay.write(stream, space_around_delimiters=False)
    files[Path("index.theme")] = stream.getvalue().encode()
    digest = hashlib.sha256()
    for relative, data in sorted(files.items()):
        digest.update(str(relative).encode() + b"\0" + data + b"\0")
    name = f"{PREFIX}{base}--{accent}--{digest.hexdigest()[:16]}"
    output.mkdir(parents=True, exist_ok=True)
    target = output / name
    if target.exists() or target.is_symlink():
        _verify_overlay(target, files)
    else:
        temporary = Path(tempfile.mkdtemp(prefix=".bgc-folders-", dir=output))
        try:
            for relative, data in files.items():
                dest = temporary / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
            try:
                _publish_directory(temporary, target)
            except FileExistsError:
                _verify_overlay(target, files)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
    return {**result, "theme": name, "icons": len(files) - 1, "status": "ready"}


def main() -> None:
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme", required=True)
    parser.add_argument("--accent", required=True)
    args = parser.parse_args()
    print(json.dumps(build_theme(args.theme, args.accent, icon_roots(), _data_home() / "icons")))


if __name__ == "__main__":
    main()
