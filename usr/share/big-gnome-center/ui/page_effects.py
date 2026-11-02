# SPDX-License-Identifier: MIT
"""
ui/page_effects.py — Pagina de Efeitos Visuais.

Mostra os controles do Frosted Glass. Extensoes de efeitos de terceiros
(Desktop Cube, Magic Lamp, Compiz Windows) ficam em Extensoes > Destaques.

DEVELOPER NOTE - DO NOT name any variable `_` in this file.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from constants import tr
from ui.frosted_glass import FrostedGlassControls, is_frosted_glass_supported


class EffectsPage(Gtk.Box):
    """Controles de efeitos visuais do proprio sistema."""

    def __init__(self, pool, toast_cb) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._pool = pool
        self._toast = toast_cb
        self._build()

    def _build(self) -> None:
        sc = Gtk.ScrolledWindow()
        sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sc.set_vexpand(True)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22)
        content.set_margin_start(22)
        content.set_margin_end(22)
        content.set_margin_top(8)
        content.set_margin_bottom(22)

        if is_frosted_glass_supported():
            content.append(FrostedGlassControls(self._pool, self._toast))
        else:
            status = Adw.StatusPage(
                icon_name="layout-effect-lamp-symbolic",
                title=tr("No visual effects available"),
                description=tr("This GNOME version does not support Frosted Glass."),
            )
            status.set_vexpand(True)
            content.append(status)

        sc.set_child(content)
        self.append(sc)
