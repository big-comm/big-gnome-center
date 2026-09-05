# SPDX-License-Identifier: MIT
"""Privileged removal of one GNOME Shell system extension."""

import os
import re
import shutil
import stat
import sys
from pathlib import Path
from typing import Optional, Sequence

SYSTEM_EXTENSION_DIR = Path("/usr/share/gnome-shell/extensions")
_UUID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+@-]*$")


def extension_target(uuid: str, base_dir: Path = SYSTEM_EXTENSION_DIR) -> Path:
    """Return the direct child selected by a valid extension UUID."""
    if not isinstance(uuid, str) or not _UUID_RE.fullmatch(uuid):
        raise ValueError("invalid extension UUID")
    return base_dir / uuid


def remove_extension(uuid: str, base_dir: Path = SYSTEM_EXTENSION_DIR) -> None:
    """Remove one directory, or one symlink, directly below ``base_dir``."""
    target = extension_target(uuid, base_dir)
    try:
        mode = target.lstat().st_mode
    except FileNotFoundError as exc:
        raise FileNotFoundError("system extension not found") from exc

    if stat.S_ISLNK(mode):
        target.unlink()
        return
    if not stat.S_ISDIR(mode):
        raise ValueError("system extension target is not a directory")
    shutil.rmtree(target)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if os.geteuid() != 0:
        print("administrator privileges are required", file=sys.stderr)
        return 77
    if len(args) != 1:
        print("usage: big-gnome-center-remove-extension UUID", file=sys.stderr)
        return 64
    try:
        remove_extension(args[0])
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
