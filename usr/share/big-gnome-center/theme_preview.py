# SPDX-License-Identifier: MIT
"""
theme_preview.py — Previews reais para linhas de temas.

Duas funcoes publicas:

  * ``find_folder_icon(theme_name)``  -> Optional[Path]
      Retorna o caminho do icone ``folder`` (svg/png) do tema de icones,
      procurando em ``scalable/places/`` e tamanhos comuns. Usado para
      mostrar uma miniatura real do icone em vez de uma bolinha arbitraria.

  * ``extract_theme_color(theme_name, kind)`` -> Optional[str]
      Extrai um hex ``#rrggbb`` representativo do tema GTK,
      parseando variaveis de cor do CSS (``@define-color accent_color``,
      ``accent_bg_color``, ``theme_selected_bg_color``, ...). Fallback para
      None quando o tema usa referencia a outra variavel ou funcao (nao
      resolvemos recursivamente).

DEVELOPER NOTE - DO NOT name any variable `_` in this file.
"""

import logging
import re
import struct
from pathlib import Path
from typing import List, Optional, Set, Tuple

log = logging.getLogger("big-gnome-center")


# ── Icon theme: folder preview ───────────────────────────────────────────────


_ICON_ROOTS: List[Path] = [
    Path.home() / ".icons",
    Path.home() / ".local" / "share" / "icons",
    Path("/usr/local/share/icons"),
    Path("/usr/share/icons"),
]

# Caminhos relativos a tentar em ordem de preferencia. SVG > PNG; places > default.
_FOLDER_REL_PATHS: List[str] = [
    "scalable/places/folder.svg",
    "scalable/places/default-folder.svg",
    "places/scalable/folder.svg",
    "48x48/places/folder.png",
    "64x64/places/folder.png",
    "32x32/places/folder.png",
    "24x24/places/folder.png",
    "scalable/places/folder-blue.svg",
]


def find_folder_icon(theme_name: str) -> Optional[Path]:
    """
    Retorna o caminho do icone ``folder`` do tema, pronto para
    ``Gtk.Picture.new_for_filename()``.

    Tenta caminhos padrao; se nenhum existir, faz glob recursivo
    procurando qualquer ``folder.svg`` ou ``folder.png``.

    Retorna None se o tema nao for encontrado ou nao tiver icone folder.
    """
    if not theme_name:
        return None

    for root in _ICON_ROOTS:
        theme_dir = root / theme_name
        if not theme_dir.is_dir():
            continue

        # Caminhos conhecidos primeiro
        for rel in _FOLDER_REL_PATHS:
            candidate = theme_dir / rel
            if candidate.is_file():
                return candidate

        # Fallback: glob recursivo limitado
        try:
            for pattern in ("folder.svg", "folder.png"):
                hits = list(theme_dir.rglob(pattern))
                if hits:
                    # Prefere hit em "places/" sobre outros locais
                    places = [h for h in hits if "places" in h.parts]
                    return places[0] if places else hits[0]
        except Exception as exc:
            log.debug("folder glob failed for %s: %s", theme_name, exc)

    return None


# ── Multi-icon strip preview ────────────────────────────────────────────────
#
# Five representative slots so the user sees what the icon theme actually
# looks like instead of just a folder. Each slot lists fixed rel paths first,
# then loose glob patterns for fallback. Inherited themes (via Index.theme
# ``Inherits=``) are walked so themes that build on Adwaita/Papirus still
# resolve icons they technically own through inheritance.

_ICON_SLOTS: List[Tuple[str, List[str], List[str]]] = [
    (
        "folder",
        [
            "scalable/places/folder.svg",
            "scalable/places/default-folder.svg",
            "places/scalable/folder.svg",
            "48x48/places/folder.png",
            "64x64/places/folder.png",
            "32x32/places/folder.png",
        ],
        ["folder.svg", "folder.png"],
    ),
    (
        "home",
        [
            "scalable/places/user-home.svg",
            "scalable/places/folder-home.svg",
            "places/scalable/user-home.svg",
            "48x48/places/user-home.png",
            "48x48/places/folder-home.png",
        ],
        ["user-home.svg", "user-home.png", "folder-home.svg"],
    ),
    (
        "text",
        [
            "scalable/mimetypes/text-x-generic.svg",
            "scalable/mimes/text-x-generic.svg",
            "scalable/mimetypes/text.svg",
            "48x48/mimetypes/text-x-generic.png",
        ],
        ["text-x-generic.svg", "text-x-generic.png"],
    ),
    (
        "browser",
        [
            "scalable/apps/firefox.svg",
            "scalable/apps/web-browser.svg",
            "scalable/apps/internet-web-browser.svg",
            "scalable/apps/org.mozilla.firefox.svg",
            "scalable/apps/google-chrome.svg",
            "48x48/apps/firefox.png",
            "48x48/apps/web-browser.png",
        ],
        ["firefox.svg", "web-browser.svg", "firefox.png", "web-browser.png"],
    ),
    (
        "settings",
        [
            "scalable/apps/preferences-system.svg",
            "scalable/apps/org.gnome.Settings.svg",
            "scalable/apps/gnome-control-center.svg",
            "scalable/apps/gnome-settings.svg",
            "scalable/categories/preferences-system.svg",
            "48x48/apps/preferences-system.png",
        ],
        [
            "preferences-system.svg",
            "org.gnome.Settings.svg",
            "preferences-system.png",
        ],
    ),
]


# Sufixos de diretorio que identificam um tema de **icones** (vs cursor).
# Cursor themes so trazem ``cursors/``; icon themes tem ao menos uma destas
# categorias num dos roots (``scalable/``, ``48x48/``, ``places/``, etc.).
_ICON_CATEGORY_DIRS = (
    "scalable",
    "symbolic",
    "places",
    "apps",
    "mimetypes",
    "mimes",
    "status",
    "devices",
    "categories",
    "actions",
    "16x16",
    "22x22",
    "24x24",
    "32x32",
    "48x48",
    "64x64",
    "96x96",
    "128x128",
    "256x256",
)


def is_icon_theme(theme_name: str) -> bool:
    """
    Retorna True se o tema (em algum root) tem ao menos um diretorio de
    categoria de icone — distingue icon themes de cursor-only themes,
    que so trazem ``cursors/`` mas tambem possuem ``index.theme``.
    """
    if not theme_name:
        return False
    for root in _ICON_ROOTS:
        theme_dir = root / theme_name
        if not theme_dir.is_dir():
            continue
        for sub in _ICON_CATEGORY_DIRS:
            if (theme_dir / sub).is_dir():
                return True
    return False


# ── Cursor theme preview ────────────────────────────────────────────────────


_XCURSOR_IMAGE_TYPE = 0xFFFD0002
_CURSOR_SLOTS: List[Tuple[str, ...]] = [
    ("default", "left_ptr", "arrow"),
    ("pointer", "hand2", "hand"),
    ("text", "xterm"),
    ("wait", "watch"),
    ("move", "fleur", "all-scroll"),
]


def is_cursor_theme(theme_name: str) -> bool:
    """Return whether a theme provides native Xcursor files."""
    if not theme_name:
        return False
    return any((root / theme_name / "cursors").is_dir() for root in _ICON_ROOTS)


def _cursor_file(theme_name: str, names: Tuple[str, ...]) -> Optional[Path]:
    for root in _ICON_ROOTS:
        cursor_dir = root / theme_name / "cursors"
        if not cursor_dir.is_dir():
            continue
        for name in names:
            candidate = cursor_dir / name
            if candidate.is_file():
                return candidate
    return None


def _decode_xcursor(path: Path, target_size: int = 24) -> Optional[Tuple[int, int, bytes]]:
    """Decode the closest static frame from an Xcursor file as RGBA bytes."""
    try:
        data = path.read_bytes()
        if len(data) < 16 or data[:4] != b"Xcur":
            return None
        header_size, version, toc_count = struct.unpack_from("<III", data, 4)
        if header_size < 16 or version > 0x00010000:
            return None
        toc_end = header_size + toc_count * 12
        if toc_end > len(data):
            return None

        images: List[Tuple[int, int]] = []
        for index in range(toc_count):
            chunk_type, nominal_size, position = struct.unpack_from(
                "<III", data, header_size + index * 12
            )
            if chunk_type == _XCURSOR_IMAGE_TYPE:
                images.append((nominal_size, position))
        images.sort(key=lambda item: (abs(item[0] - target_size), item[0] < target_size))

        for nominal_size, position in images:
            if position + 36 > len(data):
                continue
            fields = struct.unpack_from("<9I", data, position)
            chunk_header, chunk_type, subtype, chunk_version = fields[:4]
            width, height = fields[4:6]
            if (
                chunk_type != _XCURSOR_IMAGE_TYPE
                or subtype != nominal_size
                or chunk_version > 1
                or chunk_header < 36
                or not 0 < width <= 512
                or not 0 < height <= 512
            ):
                continue
            pixel_start = position + chunk_header
            pixel_end = pixel_start + width * height * 4
            if pixel_end > len(data):
                continue

            bgra = data[pixel_start:pixel_end]
            rgba = bytearray(len(bgra))
            for offset in range(0, len(bgra), 4):
                blue, green, red, alpha = bgra[offset : offset + 4]
                rgba[offset : offset + 4] = bytes((red, green, blue, alpha))
            return width, height, bytes(rgba)
    except (OSError, struct.error, ValueError) as exc:
        log.debug("cursor preview failed for %s: %s", path, exc)
    return None


def find_theme_cursors(theme_name: str) -> List[Optional[Tuple[int, int, bytes]]]:
    """Return five representative decoded cursors for a theme."""
    if not theme_name:
        return [None] * len(_CURSOR_SLOTS)
    previews: List[Optional[Tuple[int, int, bytes]]] = []
    for names in _CURSOR_SLOTS:
        cursor_file = _cursor_file(theme_name, names)
        previews.append(_decode_xcursor(cursor_file) if cursor_file else None)
    return previews


def _theme_inherits(theme_dir: Path) -> List[str]:
    """Parse Index.theme ``Inherits=`` chain. Returns empty list on failure."""
    for fname in ("index.theme", "Index.theme"):
        idx = theme_dir / fname
        if not idx.is_file():
            continue
        try:
            for line in idx.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line.startswith("Inherits="):
                    raw = line[len("Inherits=") :]
                    return [t.strip() for t in raw.split(",") if t.strip()]
        except Exception as exc:
            log.debug("inherits parse failed: %s -> %s", idx, exc)
    return []


def _find_icon_with_inheritance(
    theme_name: str,
    rel_paths: List[str],
    glob_patterns: List[str],
    _visited: Optional[Set[str]] = None,
    _depth: int = 0,
) -> Optional[Path]:
    """
    Resolve um icone seguindo a cadeia de heranca declarada em
    ``Index.theme`` (``Inherits=``). E o que o usuario ve em uso real:
    se o tema nao traz ``folder.svg``, o GNOME pega do tema herdado.
    Limita profundidade para evitar loops em temas malformados.
    """
    if _visited is None:
        _visited = set()
    if theme_name in _visited or _depth > 5:
        return None
    _visited.add(theme_name)

    inherits: List[str] = []

    for root in _ICON_ROOTS:
        theme_dir = root / theme_name
        if not theme_dir.is_dir():
            continue
        for parent in _theme_inherits(theme_dir):
            if parent not in inherits and parent not in _visited:
                inherits.append(parent)
        for rel in rel_paths:
            candidate = theme_dir / rel
            if candidate.is_file():
                return candidate

    for parent in inherits:
        found = _find_icon_with_inheritance(parent, rel_paths, glob_patterns, _visited, _depth + 1)
        if found is not None:
            return found

    # Glob recursivo so na raiz da arvore — fallback antes de desistir.
    if _depth == 0:
        for root in _ICON_ROOTS:
            theme_dir = root / theme_name
            if not theme_dir.is_dir():
                continue
            try:
                for pattern in glob_patterns:
                    hits = list(theme_dir.rglob(pattern))
                    if not hits:
                        continue
                    scalable = [h for h in hits if "scalable" in h.parts]
                    return scalable[0] if scalable else hits[0]
            except Exception as exc:
                log.debug("icon glob failed for %s/%s: %s", theme_name, pattern, exc)

    return None


def find_theme_icons(theme_name: str) -> List[Optional[Path]]:
    """
    Retorna 5 caminhos representativos do tema de icones (folder, home,
    text, browser, settings), **seguindo a cadeia de heranca**
    declarada em ``Index.theme``. Mostra o que o usuario veria de fato
    com o tema aplicado — temas que sobrescrevem poucos icones vao
    parecer semelhantes a seus pais (Adwaita/hicolor), o que e a
    realidade do uso.

    Cursor-only themes (sem diretorios de categoria de icone) devem ser
    filtrados antes via ``is_icon_theme()``.
    """
    if not theme_name:
        return [None] * len(_ICON_SLOTS)
    return [
        _find_icon_with_inheritance(theme_name, rel_paths, glob_patterns)
        for _slot, rel_paths, glob_patterns in _ICON_SLOTS
    ]


def is_dark_theme_name(theme_name: str) -> bool:
    """Heuristica rapida: o nome do tema GTK indica variante escura?"""
    n = (theme_name or "").lower()
    return any(token in n for token in ("-dark", "_dark", " dark", "noir", "night", "black"))


def is_light_theme_name(theme_name: str) -> bool:
    """Fast name heuristic for explicit light variants."""
    n = (theme_name or "").lower()
    return any(token in n for token in ("-light", "_light", " light", "white", "claro"))


# ── GTK theme: color extraction ──────────────────────────────────────────


_THEME_ROOTS: List[Path] = [
    Path.home() / ".themes",
    Path("/usr/local/share/themes"),
    Path("/usr/share/themes"),
]

# CSS variaveis em ordem de preferencia (primeira que bater ganha)
_ACCENT_VARS: List[str] = [
    "accent_bg_color",
    "accent_color",
    "theme_selected_bg_color",
    "selected_bg_color",
    "primary_color",
]

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{3,8}$")


def _css_files(theme_name: str) -> List[Path]:
    """Return candidate GTK CSS files for color extraction."""
    files: List[Path] = []
    for root in _THEME_ROOTS:
        base = root / theme_name
        if not base.is_dir():
            continue
        for sub in ("gtk-4.0/gtk.css", "gtk-3.0/gtk.css"):
            css_file = base / sub
            if css_file.is_file():
                files.append(css_file)
    return files


def _normalize_hex(value: str) -> Optional[str]:
    """Normaliza ``#rgb`` / ``#rrggbb`` / ``#rrggbbaa`` -> ``#rrggbb``."""
    value = value.strip().rstrip(";").strip()
    if not _HEX_RE.match(value):
        return None
    if len(value) == 4:  # #rgb -> #rrggbb
        return "#" + "".join(c * 2 for c in value[1:])
    return "#" + value[1:7].lower()


def _extract_from_css(text: str) -> Optional[str]:
    """Procura ``@define-color <var> <hex>`` para variaveis conhecidas."""
    for var in _ACCENT_VARS:
        pat = rf"@define-color\s+{var}\s+([^;]+);"
        match = re.search(pat, text)
        if not match:
            continue
        raw = match.group(1).strip()
        # Valor pode ser: "#rrggbb", "#rgb", "rgba(...)", "@other_var", "mix(...)"
        # So sabemos lidar com hex literal; outros casos devolvem None.
        normalized = _normalize_hex(raw)
        if normalized:
            return normalized
    return None


def extract_theme_color(theme_name: str, kind: str) -> Optional[str]:
    """
    Extrai um hex representativo do tema GTK.

    Args:
        theme_name: nome do tema (diretorio em ``~/.themes`` ou ``/usr/share/themes``)
        kind: "gtk"

    Retorna ``#rrggbb`` ou None se nao for possivel extrair uma cor literal.
    """
    if kind != "gtk":
        return None

    for css_path in _css_files(theme_name):
        try:
            # Limita leitura para nao carregar arquivos enormes inteiros
            # (gtk.css pode ter 100k+ linhas em temas grandes)
            text = css_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            log.debug("css read failed: %s -> %s", css_path, exc)
            continue

        color = _extract_from_css(text)
        if color:
            return color

    return None
