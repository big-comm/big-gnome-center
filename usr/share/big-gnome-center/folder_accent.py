# SPDX-License-Identifier: MIT
"""User-local Papient folder accents using standard icon-theme inheritance."""

import argparse
import configparser
import hashlib
import io
import os
import re
import shutil
import tempfile
from pathlib import Path

from constants import ACCENT_COLORS

BASES = ("bigicons-papient", "bigicons-papient-dark", "bigicons-papient-light")
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


def icon_roots() -> list[Path]:
    data = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    dirs = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")
    return [Path.home() / ".icons", data / "icons", *[Path(d) / "icons" for d in dirs if d]]


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
    cfg.read_string(index.read_text())
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
                if icon.stat().st_size > 1024 * 1024:
                    raise ValueError(f"Oversized folder icon: {icon.name}")
                data = icon.read_bytes()
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
        if target.is_symlink() or any(
            (target / p).is_symlink()
            or not (target / p).is_file()
            or (target / p).read_bytes() != data
            for p, data in files.items()
        ):
            raise ValueError("Managed icon theme collision")
    else:
        temporary = Path(tempfile.mkdtemp(prefix=".bgc-folders-", dir=output))
        try:
            for relative, data in files.items():
                dest = temporary / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
            temporary.rename(target)
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
    data = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    print(json.dumps(build_theme(args.theme, args.accent, icon_roots(), data / "icons")))


if __name__ == "__main__":
    main()
