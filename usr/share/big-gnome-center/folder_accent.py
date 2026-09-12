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
    files = {}
    sections = {}
    for directory in cfg.get("Icon Theme", "Directories").split(","):
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
            for svg in sorted(folder.glob("*.svg")):
                if svg.name in seen:
                    continue
                seen.add(svg.name)
                if not (
                    svg.name.startswith(("folder", "user-"))
                    or svg.name in ("desktop.svg", "inode-directory.svg")
                ):
                    continue
                if svg.stat().st_size > 1024 * 1024:
                    raise ValueError(f"Oversized folder icon: {svg.name}")
                text = svg.read_text()
                tinted, count = _HIGHLIGHT.subn(lambda m: m[1] + ACCENT_COLORS[accent] + m[2], text)
                if not count:
                    continue
                files[relative / svg.name] = tinted.encode()
                sections[directory] = dict(cfg[directory])
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
        "Directories": ",".join(sections),
    }
    for name, values in sections.items():
        overlay[name] = values
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
