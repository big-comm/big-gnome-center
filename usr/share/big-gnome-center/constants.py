# SPDX-License-Identifier: MIT
"""
constants.py — Constantes globais, dados de configuração e setup de i18n.

DEVELOPER NOTE — DO NOT name any variable `_` in this file.
`tr = gettext.gettext` is the translation function. Use named throwaway
variables: ok, err, out, val, raw, data, info, etc.
"""

import gettext
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

# ── i18n ──────────────────────────────────────────────────────────────────────
# gettext.gettext() do modulo nao respeita bindtextdomain — precisamos do
# gettext.translation(domain, localedir).gettext para usar nossos .mo.
#
# Procura a pasta locale em varias raizes e testa se o .mo do dominio existe
# em pelo menos um idioma. Assim evitamos cair em /usr/share/locale quando ele
# nao contem o dominio do app.
_DOMAIN = "big-gnome-center"


def _find_locale_dir() -> str:
    # Arquivo fica em <share>/big-gnome-center/, logo parent^2 = <share>.
    # Tanto em dev (repo/usr/share) quanto em instalacao (/usr/share), o .mo
    # fica em <share>/locale/<lang>/LC_MESSAGES/big-gnome-center.mo — mesma
    # logica.
    _script = Path(__file__).resolve()
    candidates = [
        _script.parent.parent / "locale",
        Path("/usr/share/locale"),
        Path("/usr/local/share/locale"),
        Path.home() / ".local" / "share" / "locale",
    ]
    for base in candidates:
        if not base.is_dir():
            continue
        if any(base.glob(f"*/LC_MESSAGES/{_DOMAIN}.mo")):
            return str(base)
    return "/usr/share/locale"


_LOCALE_DIR = _find_locale_dir()
gettext.bindtextdomain(_DOMAIN, _LOCALE_DIR)
gettext.textdomain(_DOMAIN)
tr = gettext.translation(_DOMAIN, _LOCALE_DIR, fallback=True).gettext  # purposely NOT named `_`

# ── Aplicação ─────────────────────────────────────────────────────────────────
APP_ID = "br.com.biglinux.BigGnomeCenter"
APP_VERSION = "3.0.1"
APP_LICENSE = "MIT"
APP_NAME = "Big Gnome Center"
ICON_NAME = "big-gnome-center"
DESKTOP_ID = "br.com.biglinux.BigGnomeCenter.desktop"
LEGACY_DESKTOP_ID = "org.communitybig.layout-switcher.desktop"

# ── Diretórios de dados ───────────────────────────────────────────────────────
def _migrate_legacy_dir(old: Path, new: Path) -> None:
    """Copy pre-rebrand user data once, without deleting or replacing it."""
    if new.exists() or new.is_symlink() or not old.is_dir():
        return
    try:
        new.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f".{new.name}.", dir=new.parent) as temporary:
            staged = Path(temporary) / "data"
            shutil.copytree(old, staged, symlinks=True)
            if not new.exists() and not new.is_symlink():
                staged.rename(new)
    except OSError:
        pass


def _replace_legacy_desktop_id(apps: List[str]) -> List[str]:
    """Replace the former launcher ID while preserving folder order."""
    migrated: List[str] = []
    for desktop_id in apps:
        if desktop_id == LEGACY_DESKTOP_ID:
            desktop_id = DESKTOP_ID
        if desktop_id not in migrated:
            migrated.append(desktop_id)
    return migrated


def _migrate_settings_app_folder() -> None:
    """Keep the renamed launcher in the user's existing Settings folder."""
    try:
        from gi.repository import Gio

        settings = Gio.Settings.new_with_path(
            "org.gnome.desktop.app-folders.folder",
            "/org/gnome/desktop/app-folders/folders/Settings/",
        )
        apps = list(settings.get_strv("apps"))
        migrated = _replace_legacy_desktop_id(apps)
        if migrated != apps:
            settings.set_strv("apps", migrated)
    except Exception:
        # App folders are optional and may not exist outside GNOME sessions.
        pass


def migrate_user_data() -> None:
    """Import settings and cache from the former application name."""
    _migrate_legacy_dir(Path.home() / ".config" / "big-appearance", CONFIG_DIR)
    _migrate_legacy_dir(Path.home() / ".cache" / "layout-switcher", CACHE_DIR)
    _migrate_settings_app_folder()


# Instalação em /usr/share ou ~/.local/share
_SHARE_DIRS = [
    Path(__file__).parent,  # package directory
    Path.home() / ".local" / "share" / "big-gnome-center",
    Path("/usr/share/big-gnome-center"),
    Path("/usr/local/share/big-gnome-center"),
]

CONFIG_DIR = Path.home() / ".config" / "big-gnome-center"
CACHE_DIR = Path.home() / ".cache" / "big-gnome-center"
BACKUP_DIR = CONFIG_DIR / "backups"
SETTINGS_FILE = CONFIG_DIR / "settings.json"

EGO_CACHE_DIR = CACHE_DIR / "ego"
EGO_THUMBS_DIR = CACHE_DIR / "thumbs"

LAYOUTS_DIR = "layouts"
ICONS_DIR = "icons"

# ── extensions.gnome.org ──────────────────────────────────────────────────────
EGO_BASE_URL = "https://extensions.gnome.org"
EGO_USER_AGENT = "BigGnomeCenter/{version} (+https://communitybig.org)"
EGO_CACHE_TTL_SEARCH = 60 * 60  # 1h
EGO_CACHE_TTL_INFO = 60 * 60 * 24  # 24h
EGO_THUMBS_MAX_BYTES = 50 * 1024 * 1024  # 50 MiB
UPDATE_CHECK_INTERVAL = 60 * 60 * 12  # 12h

# ── Diretórios de extensões GNOME ─────────────────────────────────────────────
EXT_USER_DIR = Path.home() / ".local" / "share" / "gnome-shell" / "extensions"
EXT_SYS_DIR = Path("/usr/share/gnome-shell/extensions")

# ── D-Bus ─────────────────────────────────────────────────────────────────────
DBUS_SHELL_NAME = "org.gnome.Shell"
DBUS_SHELL_PATH = "/org/gnome/Shell"
DBUS_EXT_IFACE = "org.gnome.Shell.Extensions"
DBUS_EVAL_IFACE = "org.gnome.Shell.Eval"  # legacy, ainda funciona GS < 46
DBUS_EXT_PATH = "/org/gnome/Shell"

# ── Mapa de cores para temas ──────────────────────────────────────────────────
ACCENT_COLORS: Dict[str, str] = {
    "blue": "#3584e4",
    "teal": "#2190a4",
    "green": "#3a944a",
    "yellow": "#c88800",
    "orange": "#ed5b00",
    "red": "#e62d42",
    "pink": "#d56199",
    "purple": "#9141ac",
    "slate": "#6f8396",
    "maia": "#16a085",
}

COLOR_MAP: Dict[str, str] = {
    "blue": "#3584e4",
    "green": "#26a269",
    "yellow": "#cd9309",
    "orange": "#e66100",
    "red": "#c01c28",
    "purple": "#9141ac",
    "pink": "#d16d9e",
    "teal": "#2190a4",
    "grey": "#5e5c64",
    "gray": "#5e5c64",
    "black": "#241f31",
    "white": "#f6f5f4",
    "dark": "#241f31",
    "light": "#deddda",
    "brown": "#865e3c",
    "cyan": "#00b4c8",
    "magenta": "#c061cb",
    "lime": "#2ec27e",
    "indigo": "#1c71d8",
    "nord": "#5e81ac",
    "dracula": "#bd93f9",
    "catppuccin": "#cba6f7",
    "gruvbox": "#d79921",
    "solarized": "#268bd2",
    "arc": "#5294e2",
    "materia": "#2196f3",
    "numix": "#f05542",
    "pop": "#48b9c7",
    "yaru": "#e95420",
    "breeze": "#3daee9",
    "adwaita": "#3584e4",
    "gnome": "#4a86cf",
    "ubuntu": "#e95420",
    "fedora": "#3c6eb4",
}

# ── Extensões em destaque ─────────────────────────────────────────────────────
FEATURED_EXTENSIONS: List[Dict] = [
    {
        "name": tr("Desktop Cube"),
        "description": tr("Rotate workspaces on a 3D cube"),
        "uuid": "desktop-cube@schneegans.github.com",
        "ego_id": 4648,
        "pkg": "gnome-shell-extension-desktop-cube",
        "icon": "layout-effect-cube-symbolic",
        "author": "Simon Schneegans",
        "has_settings": False,
        "preview": "cube",
    },
    {
        "name": tr("Magic Lamp"),
        "description": tr("Genie effect when minimizing windows"),
        "uuid": "compiz-alike-magic-lamp-effect@hermes83.github.com",
        "ego_id": 3740,
        "pkg": "gnome-shell-extension-compiz-alike-magic-lamp-effect",
        "icon": "layout-effect-genie-lamp-symbolic",
        "author": "hermes83",
        "has_settings": False,
        "preview": "lamp",
    },
    {
        "name": tr("Compiz Windows"),
        "description": tr("Wobbly windows and extra animations"),
        "uuid": "compiz-windows-effect@hermes83.github.com",
        "ego_id": 3210,
        "pkg": "gnome-shell-extension-compiz-windows-effect",
        "icon": "layout-effect-wobbly-symbolic",
        "author": "hermes83",
        "has_settings": False,
        "preview": "wobbly",
    },
]

EFFECT_EXTENSIONS: List[Dict] = [
    ext for ext in FEATURED_EXTENSIONS if ext.get("preview") in ("cube", "lamp", "wobbly")
]

# Layouts shown in the grid but greyed out and not clickable.
# Use for work-in-progress layouts that should remain visible to users
# (so they know it's coming) but can't be applied yet.
DISABLED_LAYOUTS: List[str] = []

# ── Layouts: (name, config_file, icon_svg, icon_fallback, description) ────────
LAYOUTS: List[Tuple[str, str, str, str, str]] = [
    (
        "BigGnome",
        "biggnome.txt",
        "biggnome.svg",
        "view-paged-symbolic",
        tr("Default Big Gnome layout"),
    ),
    (
        "Desk UX",
        "desk-ux.txt",
        "desk-ux.svg",
        "view-grid-symbolic",
        tr("Clean and contemporary desktop"),
    ),
    (
        "Hybrid",
        "hybrid.txt",
        "hybrid.svg",
        "view-dual-symbolic",
        tr("Centered dock-taskbar, Windows 11 / Deepin / Pop!_OS style"),
    ),
    (
        "G-Unity",
        "g-unity.txt",
        "g-unity.svg",
        "view-app-grid-symbolic",
        tr("Unity-style layout with left dock and top bar"),
    ),
    (
        "Classic",
        "classic.txt",
        "classic.svg",
        "view-continuous-symbolic",
        tr("Traditional desktop with taskbar and system tray"),
    ),
    (
        "Minimal",
        "minimal.txt",
        "minimal.svg",
        "view-grid-symbolic",
        tr("Near-vanilla GNOME with minimal distro tweaks"),
    ),
]
