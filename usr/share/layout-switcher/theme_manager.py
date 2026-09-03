# SPDX-License-Identifier: MIT
"""Manage native accent, color-scheme, GTK, and icon themes."""

import ast
from pathlib import Path
from typing import List, Tuple

from constants import ACCENT_COLORS
from settings_store import Settings
from shell_reloader import ShellReloader
from theme_preview import is_icon_theme
from utils import gsettings_get, gsettings_set

_SHELL_SCHEMA = "org.gnome.shell"
_LIGHT_STYLE_UUID = "light-style@gnome-shell-extensions.gcampax.github.com"
_USER_THEME_UUID = "user-theme@gnome-shell-extensions.gcampax.github.com"
_SHELL_DARK_LAYOUTS = {
    "BigGnome",
    "Desk UX",
    "Desk-UX",
    "G-Unity",
    "Minimal",
}


class ThemeMgr:
    """
    Gerencia temas GTK, ícones e Shell do GNOME.

    Todos os métodos apply_* propagam mudanças em tempo real
    sem encerrar a sessão.
    """

    @staticmethod
    def _layout_snapshot_marker() -> Path:
        """Return the marker for the last layout-managed settings snapshot."""
        return Path.home() / ".config" / "dconf" / "settings.gnome.layout-switcher.sha256"

    @staticmethod
    def _invalidate_layout_snapshot() -> None:
        """Mark live settings as user-modified for the next final dconf save."""
        try:
            ThemeMgr._layout_snapshot_marker().unlink(missing_ok=True)
        except OSError:
            # Theme application must not fail only because persistence
            # bookkeeping is temporarily unavailable.
            pass

    # ── Listar temas disponíveis ──────────────────────────────────────────────

    @staticmethod
    def _is_valid_theme(d: Path, kind: str) -> bool:
        """Check if directory d contains a valid theme of given kind."""
        if kind == "gtk":
            return any((d / sub).exists() for sub in ("gtk-4.0", "gtk-3.0", "gtk-2.0"))
        if kind == "icons":
            # ``index.theme`` sozinho aceita tambem temas de cursor (ex.: Bibata),
            # que so trazem ``cursors/``. Exige que o tema tenha pelo menos
            # uma categoria de icone para nao poluir a aba Icones.
            return (d / "index.theme").exists() and is_icon_theme(d.name)
        return False

    @staticmethod
    def _theme_roots(kind: str) -> List[Path]:
        """Return search directories for theme kind."""
        if kind == "gtk":
            return [
                Path.home() / ".themes",
                Path("/usr/local/share/themes"),
                Path("/usr/share/themes"),
            ]
        return [
            Path.home() / ".icons",
            Path("/usr/local/share/icons"),
            Path("/usr/share/icons"),
        ]

    @staticmethod
    def list_themes(kind: str) -> List[str]:
        """
        Lista temas instalados do tipo especificado.
        kind: "gtk" | "icons"
        """
        seen: dict = {}
        for root in ThemeMgr._theme_roots(kind):
            if not root.is_dir():
                continue
            try:
                entries = list(root.iterdir())
            except PermissionError:
                continue
            for d in entries:
                if not d.is_dir() or d.name.startswith(".") or d.name in seen:
                    continue
                if ThemeMgr._is_valid_theme(d, kind):
                    seen[d.name] = True

        names = sorted(seen.keys(), key=str.lower)
        return names

    # ── Aplicar tema ──────────────────────────────────────────────────────────

    @staticmethod
    def apply(kind: str, name: str) -> Tuple[bool, str]:
        """
        Aplica o tema especificado em tempo real via gsettings.

        Para GTK/ícones: propaga imediatamente para todas as janelas abertas.
        Retorna (True, "") ou (False, código_erro).
        """
        if kind == "gtk":
            ok, msg = gsettings_set("org.gnome.desktop.interface", "gtk-theme", name)
            if ok:
                ThemeMgr._invalidate_layout_snapshot()
            return ok, msg

        if kind == "icons":
            ok, msg = gsettings_set("org.gnome.desktop.interface", "icon-theme", name)
            if ok:
                ThemeMgr._invalidate_layout_snapshot()
            return ok, msg

        return False, f"unknown theme kind: {kind!r}"

    # ── Esquema de cores ──────────────────────────────────────────────────────

    @staticmethod
    def set_accent_color(color: str) -> Tuple[bool, str]:
        """Apply the native GNOME accent."""
        if color not in ACCENT_COLORS:
            return False, f"unknown accent color: {color!r}"

        ok, msg = gsettings_set(
            "org.gnome.desktop.interface",
            "accent-color",
            color,
        )
        if ok:
            ThemeMgr._invalidate_layout_snapshot()
        return ok, msg

    @staticmethod
    def accent_color() -> str:
        """Return the active GNOME accent color."""
        color = gsettings_get("org.gnome.desktop.interface", "accent-color")
        return color if color in ACCENT_COLORS else "blue"

    @staticmethod
    def set_color_scheme(dark: bool) -> Tuple[bool, str]:
        """
        Define esquema de cores claro/escuro.
        Propaga imediatamente para todas as janelas GTK4/libadwaita abertas
        e notifica o Adw.StyleManager em processo.
        """
        scheme = "prefer-dark" if dark else "prefer-light"
        ok, msg = gsettings_set("org.gnome.desktop.interface", "color-scheme", scheme)
        if ok:
            active_layout = Settings().get("active_layout")
            shell_dark = dark or active_layout in _SHELL_DARK_LAYOUTS
            ThemeMgr._sync_shell_color_scheme(
                shell_dark,
                fixed_shell=active_layout in _SHELL_DARK_LAYOUTS,
            )
            # Notifica o StyleManager do processo atual
            try:
                import gi

                gi.require_version("Adw", "1")
                from gi.repository import Adw

                mgr = Adw.StyleManager.get_default()
                if dark:
                    mgr.set_color_scheme(Adw.ColorScheme.PREFER_DARK)
                else:
                    mgr.set_color_scheme(Adw.ColorScheme.PREFER_LIGHT)
            except Exception:
                pass
            ThemeMgr._invalidate_layout_snapshot()
        return ok, msg

    @staticmethod
    def _string_list(value: str | None) -> List[str]:
        if not value:
            return []
        try:
            parsed = ast.literal_eval(value.strip())
        except (ValueError, SyntaxError):
            return []
        if not isinstance(parsed, list):
            return []
        return [item for item in parsed if isinstance(item, str) and item]

    @staticmethod
    def _sync_shell_color_scheme(
        dark: bool,
        *,
        fixed_shell: bool = False,
    ) -> None:
        enabled = ThemeMgr._string_list(gsettings_get(_SHELL_SCHEMA, "enabled-extensions"))
        disabled = ThemeMgr._string_list(gsettings_get(_SHELL_SCHEMA, "disabled-extensions"))

        def add_once(values: List[str], uuid: str) -> None:
            if uuid not in values:
                values.append(uuid)

        enabled = [uuid for uuid in enabled if uuid != _USER_THEME_UUID]
        add_once(disabled, _USER_THEME_UUID)

        if dark or fixed_shell:
            enabled = [uuid for uuid in enabled if uuid != _LIGHT_STYLE_UUID]
            add_once(disabled, _LIGHT_STYLE_UUID)
        else:
            disabled = [uuid for uuid in disabled if uuid != _LIGHT_STYLE_UUID]
            add_once(enabled, _LIGHT_STYLE_UUID)

        gsettings_set("org.gnome.shell.extensions.user-theme", "name", "''")
        gsettings_set(_SHELL_SCHEMA, "disabled-extensions", repr(disabled))
        gsettings_set(_SHELL_SCHEMA, "enabled-extensions", repr(enabled))
        ShellReloader.reload_extension(_LIGHT_STYLE_UUID, timeout=5)

    # ── Consultas ─────────────────────────────────────────────────────────────

    @staticmethod
    def current(kind: str) -> str:
        """Retorna o nome do tema atualmente ativo para o tipo informado."""
        key_map = {
            "gtk": ("org.gnome.desktop.interface", "gtk-theme"),
            "icons": ("org.gnome.desktop.interface", "icon-theme"),
        }
        schema, key = key_map.get(kind, ("", ""))
        if not schema:
            return ""
        value = gsettings_get(schema, key) or ""
        return value

    @staticmethod
    def color_scheme() -> str:
        """Retorna o esquema de cores atual: 'prefer-dark' ou 'prefer-light'."""
        return gsettings_get("org.gnome.desktop.interface", "color-scheme") or "prefer-light"
