# SPDX-License-Identifier: MIT
"""Reversible GTK background styles for validated applications."""

import argparse
import os
import stat
import sys
import tempfile
from pathlib import Path

OWNER = b"/* Big Gnome Center window material. */\n"
NAME = "big-gnome-center-windows.css"
IMPORT = (
    '/* BEGIN Big Gnome Center windows */\n'
    f'@import url("{NAME}");\n'
    '/* END Big Gnome Center windows */\n'
).encode()
WINDOW_CLASSES = (
    "nautilus-window", "big-gnome-center", "org-gnome-TextEditor",
    "big-audio-converter", "big-video-converter", "big-hardware-info",
    "big-network-info", "bigocrpdf", "bigocrimage", "bigocrpdf-editor",
    "biglinux-webapps", "biglinux-settings", "bigrecorder",
)
SELECTORS = ", ".join(f"window.{name}" for name in WINDOW_CLASSES)
DIALOG_SELECTORS = ", ".join(f"window.{name} dialog" for name in WINDOW_CLASSES)


def render_css(opacity: int) -> bytes:
    """Tint backgrounds only; keep foreground and widget states untouched."""
    alpha = (60 + max(0, min(100, opacity)) * 0.4) / 100
    return OWNER + f"""@media (prefers-contrast: no-preference) {{
    {SELECTORS} {{
        --window-bg-color: transparent;
        --view-bg-color: transparent;
        --headerbar-bg-color: transparent;
        --headerbar-backdrop-color: transparent;
        --sidebar-bg-color: alpha(@window_bg_color, 0.20);
        --sidebar-backdrop-color: alpha(@window_bg_color, 0.20);
        background-color: alpha(@window_bg_color, {alpha:.2f});
        backdrop-filter: blur(30px);
    }}
    {DIALOG_SELECTORS} {{
        --window-bg-color: @window_bg_color;
        --view-bg-color: @view_bg_color;
        --headerbar-bg-color: @headerbar_bg_color;
        --headerbar-backdrop-color: @headerbar_backdrop_color;
        --sidebar-bg-color: @sidebar_bg_color;
        --sidebar-backdrop-color: @sidebar_backdrop_color;
    }}
    window.bigrecorder .app-bg,
    window.bigrecorder .flat-header,
    window.bigrecorder .flat-toolbar,
    window.bigrecorder headerbar,
    window.bigrecorder windowhandle,
    window.bigrecorder .titlebar {{
        background-color: var(--window-bg-color);
    }}
    window.org-gnome-TextEditor textview,
    window.org-gnome-TextEditor textview text {{
        background-color: transparent;
    }}
    window.ashyterm-window {{
        backdrop-filter: blur(30px);
    }}
}}
""".encode()


def gtk_supports_blur() -> bool:
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    if Gtk.check_version(4, 23, 3) is not None:
        return False
    errors = []
    provider = Gtk.CssProvider()
    provider.connect("parsing-error", lambda *args: errors.append(args[-1]))
    provider.load_from_string(render_css(37).decode())
    return not errors


def read_regular(path: Path) -> bytes | None:
    if path.is_symlink():
        raise ValueError(f"Refusing CSS symlink: {path}")
    try:
        if not stat.S_ISREG(path.stat().st_mode):
            raise ValueError(f"Refusing non-regular CSS: {path}")
        return path.read_bytes()
    except FileNotFoundError:
        return None


def replace_checked(path: Path, content: bytes, previous: bytes | None) -> None:
    if previous == content:
        return
    mode = stat.S_IMODE(path.stat().st_mode) if previous is not None else 0o600
    fd, temporary = tempfile.mkstemp(prefix=".bgc-windows-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fchmod(stream.fileno(), mode)
        if read_regular(path) != previous:
            raise ValueError(f"CSS changed during update: {path}")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def sync_styles(config_dir: Path, enabled: bool, opacity: int = 37) -> None:
    directory = config_dir / "gtk-4.0"
    if directory.is_symlink():
        raise ValueError(f"Refusing GTK directory symlink: {directory}")
    if not directory.exists() and not enabled:
        return
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / NAME
    entry = directory / "gtk.css"
    original = read_regular(entry)
    material = read_regular(target)
    if material is not None and not material.startswith(OWNER):
        raise ValueError(f"Refusing unowned material file: {target}")
    user_css = original or b""
    if enabled and b"/* BEGIN Big Gnome Center windows */" in user_css and IMPORT not in user_css:
        raise ValueError("Managed CSS import was edited; preserving user changes")
    if enabled:
        replace_checked(target, render_css(opacity), material)
        if IMPORT not in user_css:
            # Preserve a UTF-8 BOM and all user bytes after our import.
            bom = b"\xef\xbb\xbf" if user_css.startswith(b"\xef\xbb\xbf") else b""
            replace_checked(entry, bom + IMPORT + user_css[len(bom):], original)
    else:
        # Empty our sheet first so stale imports stay harmless.
        if material is not None:
            replace_checked(target, OWNER, material)
        if IMPORT in user_css:
            replace_checked(entry, user_css.replace(IMPORT, b""), original)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable", action="store_true")
    parser.add_argument("--opacity", type=int, default=37)
    args = parser.parse_args()
    config_dir = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    try:
        supported = not args.enable or gtk_supports_blur()
        sync_styles(config_dir, args.enable and supported, args.opacity)
        if not supported:
            print("Window material requires GTK 4.23.3 with backdrop-filter", file=sys.stderr)
        return 0
    except (OSError, ValueError, ImportError) as error:
        print(f"Window material: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
