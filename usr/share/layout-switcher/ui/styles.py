# SPDX-License-Identifier: MIT
"""
ui/styles.py — CSS da aplicação.

Centraliza todo o estilo visual para facilitar customização e manutenção.
Carregado uma única vez em MainWindow._apply_css().

DEVELOPER NOTE — DO NOT name any variable `_` in this file.
"""

APP_CSS = """
/* ── Sidebar ─────────────────────────────────────────────────────────── */
.nav-row {
    border-radius: 10px;
    margin: 1px 7px;
    transition: background-color 120ms ease;
}
.nav-row:hover              { background-color: alpha(@accent_bg_color, 0.08); }
.nav-row:focus              { outline: 2px solid alpha(@accent_color, 0.5); outline-offset: -2px; }
.nav-row.nav-sel            { background-color: alpha(@accent_bg_color, 0.17); }
.nav-row.nav-sel .nav-lbl   { color: @accent_color; font-weight: 700; }
.nav-lbl                    { font-weight: 500; }

/* ── Layout cards ────────────────────────────────────────────────────── */
.layout-card {
    background-color: alpha(@card_bg_color, 0.50);
    border: 1px solid alpha(@card_fg_color, 0.10);
    border-radius: 15px;
    padding: 10px 10px 13px;
    transition: background-color 160ms ease,
                border-color 160ms ease,
                box-shadow 200ms ease;
    box-shadow: 0 1px 2px alpha(black, 0.05);
}
.layout-card:hover {
    background-color: alpha(@card_bg_color, 0.92);
    border-color: alpha(@accent_color, 0.42);
    box-shadow: 0 8px 22px alpha(black, 0.16);
}
.layout-card.layout-on {
    border-color: @accent_color;
    background-color: alpha(@accent_bg_color, 0.10);
    box-shadow: 0 0 0 1px @accent_color,
                0 8px 24px alpha(@accent_color, 0.20);
}

/* Preview (SVG wrapper) — só arredonda. A seleção vive no card, então o
   preview NÃO ganha contorno próprio (evita o contorno duplo: um interno
   no preview + um externo na borda do card). */
.layout-preview {
    border-radius: 10px;
}

/* Neutraliza a seleção/contorno nativo do FlowBoxChild para não somar com
   a borda do card — a única seleção visível é a do .layout-card. */
.layout-grid > flowboxchild {
    outline: none;
    background: none;
    box-shadow: none;
    border-radius: 15px;
}
.layout-grid > flowboxchild:hover,
.layout-grid > flowboxchild:focus,
.layout-grid > flowboxchild:focus-visible,
.layout-grid > flowboxchild:selected {
    background: none;
    box-shadow: none;
    outline: none;
}

/* Disabled layout (work-in-progress, not yet clickable) */
.layout-disabled                     { opacity: 0.42; }
.layout-disabled:hover {
    background-color: alpha(@card_bg_color, 0.50);
    border-color: alpha(@card_fg_color, 0.10);
    box-shadow: 0 1px 2px alpha(black, 0.05);
}
.layout-disabled:hover .layout-preview { box-shadow: none; }

/* Nome do layout (descrição agora aparece só no hover) */
.layout-name                         { font-weight: 700; }
.layout-name-active                  { color: @accent_color; font-weight: 800; letter-spacing: 0; }

/* Badge "Modified" theme-aware (libadwaita adapta @warning_bg/fg_color) */
.layout-modified-badge {
    background-color: @warning_bg_color;
    color: @warning_fg_color;
    border: 1px solid alpha(@warning_fg_color, 0.22);
    border-radius: 6px;
    padding: 1px 7px;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0;
    box-shadow: 0 1px 2px alpha(#000000, 0.15);
}
.layout-modified-badge image,
.layout-modified-badge label {
    color: @warning_fg_color;
}

/* Check de ativo — circulo accent no canto superior-direito do preview */
.layout-active-check {
    /* Green "done" check — matches the checkmark the in-shell transition
       curtain flashes when the switch completes. */
    background-color: @success_color;
    color: white;
    border-radius: 50%;
    padding: 3px;
    box-shadow: 0 0 8px alpha(@success_color, 0.55);
}

/* ── Community Menu style chooser ───────────────────────────────────── */
.menu-style-grid > flowboxchild {
    background: none;
    outline: none;
    box-shadow: none;
}
.menu-style-card {
    padding: 0;
    border-radius: 12px;
    border: 1px solid alpha(@card_fg_color, 0.12);
    background-color: alpha(@card_bg_color, 0.54);
    box-shadow: none;
}
.menu-style-card:hover {
    border-color: alpha(@accent_color, 0.48);
    background-color: alpha(@card_bg_color, 0.82);
}
.menu-style-card:checked {
    border-color: @accent_color;
    background-color: alpha(@accent_bg_color, 0.13);
    box-shadow: inset 0 0 0 1px @accent_color;
}
.menu-style-preview-stage {
    border-radius: 8px;
    background-color: #17171c;
    border: 1px solid alpha(white, 0.08);
}
.menu-style-preview {
    padding: 5px;
    border-radius: 7px;
    background-color: #27272d;
    border: 1px solid alpha(white, 0.10);
    box-shadow: 0 2px 5px alpha(black, 0.35);
}
.menu-style-preview-classic {
    border-radius: 7px 7px 3px 3px;
}
.menu-style-preview-desk-ux {
    border-radius: 7px;
}
.menu-style-preview-hybrid {
    border-radius: 7px 7px 3px 3px;
}
.menu-style-search {
    border-radius: 5px;
    background-color: alpha(white, 0.22);
}
.menu-style-rail,
.menu-style-categories {
    padding: 3px;
    border-radius: 4px;
    background-color: alpha(white, 0.10);
}
.menu-style-rail-item {
    border-radius: 50%;
    background-color: alpha(#3584e4, 0.88);
}
.menu-style-category-line {
    border-radius: 2px;
    background-color: alpha(white, 0.34);
}
.menu-style-app {
    border-radius: 3px;
    background-color: alpha(#3584e4, 0.82);
}
.menu-style-user {
    border-radius: 3px;
    background-color: alpha(white, 0.36);
}
.menu-style-footer {
    padding-top: 3px;
    border-top: 1px solid alpha(white, 0.13);
}
.menu-style-actions {
    padding: 2px;
}
.menu-style-action {
    border-radius: 50%;
    background-color: alpha(white, 0.58);
}
.menu-style-divider {
    background-color: alpha(white, 0.18);
}
.menu-style-default {
    padding: 2px 8px;
    border-radius: 999px;
    background-color: alpha(@accent_bg_color, 0.50);
    color: @accent_fg_color;
    font-size: 10px;
    font-weight: 700;
}

/* ── Notification position chooser ──────────────────────────────────── */
.notification-position-grid > flowboxchild {
    background: none;
    outline: none;
    box-shadow: none;
}
.notification-position-card {
    padding: 0;
    border-radius: 12px;
    border: 1px solid alpha(@card_fg_color, 0.12);
    background-color: alpha(@card_bg_color, 0.54);
    box-shadow: none;
}
.notification-position-card:hover {
    border-color: alpha(@accent_color, 0.48);
    background-color: alpha(@card_bg_color, 0.82);
}
.notification-position-card:checked {
    border-color: @accent_color;
    background-color: alpha(@accent_bg_color, 0.13);
    box-shadow: inset 0 0 0 1px @accent_color;
}
.notification-position-preview {
    border-radius: 8px;
    background-color: #17171c;
    border: 1px solid alpha(white, 0.08);
}
.notification-position-desktop {
    margin: 5px;
    border-radius: 5px;
    background-color: #27272d;
    border: 1px solid alpha(white, 0.10);
}
.notification-position-panel {
    min-height: 4px;
    margin: 6px;
    border-radius: 3px;
    background-color: alpha(white, 0.22);
}
.notification-position-banner {
    border-radius: 5px;
    background-color: alpha(@accent_bg_color, 0.88);
    border: 1px solid alpha(@accent_fg_color, 0.30);
    box-shadow: 0 2px 5px alpha(black, 0.35);
}

/* ── Community Dock running indicator chooser ──────────────────────── */
.indicator-style-grid > flowboxchild {
    background: none;
    outline: none;
    box-shadow: none;
}
.indicator-style-card {
    padding: 0;
    border-radius: 12px;
    border: 1px solid alpha(@card_fg_color, 0.12);
    background-color: alpha(@card_bg_color, 0.54);
    box-shadow: none;
}
.indicator-style-card:hover {
    border-color: alpha(@accent_color, 0.48);
    background-color: alpha(@card_bg_color, 0.82);
}
.indicator-style-card:checked {
    border-color: @accent_color;
    background-color: alpha(@accent_bg_color, 0.13);
    box-shadow: inset 0 0 0 1px @accent_color;
}
.indicator-style-preview {
    padding: 6px;
    border-radius: 8px;
    background-color: #17171c;
    border: 1px solid alpha(white, 0.08);
}
.indicator-preview-icon {
    border-radius: 7px;
    background-color: #5e606a;
    border: 1px solid alpha(white, 0.12);
}
.indicator-preview-mark {
    min-height: 3px;
    border-radius: 999px;
    background-color: alpha(#b8bac2, 0.70);
}
.indicator-preview-active {
    background-color: @accent_bg_color;
}
.indicator-preview-dot {
    min-width: 6px;
    min-height: 6px;
}
.indicator-preview-hybrid {
    min-width: 20px;
    min-height: 4px;
}
.indicator-preview-desk-ux.indicator-preview-inactive {
    min-width: 8px;
}
.indicator-preview-desk-ux.indicator-preview-active {
    min-width: 20px;
}

/* ── Extension cards em destaque ─────────────────────────────────────── */
.ext-card {
    outline: 1px solid alpha(@card_fg_color, 0.12);
    outline-offset: -1px;
    border-radius: 14px;
    background-color: alpha(@card_bg_color, 0.52);
    transition: outline-color 120ms ease, background-color 120ms ease;
}
.ext-card:hover             { background-color: alpha(@card_bg_color, 0.78); }
.ext-card.ext-on            { outline: 2px solid @accent_color; outline-offset: -2px; }
.effect-preview-image       { border-radius: 10px; background-color: #080b12; }
.effect-icon-frame {
    border-radius: 11px;
    background-color: alpha(@card_bg_color, 0.42);
    outline: 1px solid alpha(@card_fg_color, 0.14);
    outline-offset: -1px;
}

/* ── Lista de extensões instaladas (boxed-list nativo) ───────────────── */
/* As linhas usam Gtk.ListBoxRow dentro de .boxed-list — sem esticar.    */
.boxed-list > row:hover     { background-color: alpha(@accent_bg_color, 0.05); }
.extension-action-button {
    min-width: 34px;
    min-height: 34px;
    padding: 0;
    border-radius: 8px;
}
.extension-action-button-disabled {
    opacity: 0.38;
}

/* ── Lista de temas (boxed-list nativo) ──────────────────────────────── */
.boxed-list > row.activatable:hover { background-color: alpha(@accent_bg_color, 0.06); }
.theme-name-active          { color: @accent_color; font-weight: 600; }

/* ── Grid de temas (GTK / Shell) ─────────────────────────────────────── */
.theme-surface {
    border-radius: 14px;
    background-color: alpha(@card_bg_color, 0.34);
    outline: 1px solid alpha(@card_fg_color, 0.08);
    outline-offset: -1px;
}
.theme-tile {
    outline: 1px solid alpha(@card_fg_color, 0.10);
    outline-offset: -1px;
    border-radius: 10px;
    background-color: alpha(@card_bg_color, 0.46);
    transition: outline-color 120ms ease, background-color 120ms ease, box-shadow 120ms ease;
}
.theme-tile:hover {
    background-color: alpha(@card_bg_color, 0.78);
    box-shadow: 0 5px 14px alpha(black, 0.13);
}
.theme-tile.theme-tile-active { outline: 2px solid @accent_color; outline-offset: -2px; }
.theme-active-check {
    color: white;
    background-color: @accent_bg_color;
    border-radius: 50%;
    padding: 3px;
    box-shadow: 0 2px 6px alpha(black, 0.28);
}
.theme-icon-preview {
    border-radius: 7px;
    background-color: alpha(@window_bg_color, 0.72);
    outline: 1px solid alpha(@window_fg_color, 0.08);
    outline-offset: -1px;
}

/* ── Seletor de cor de realce ───────────────────────────────────────── */
.accent-color-card {
    border-radius: 12px;
    background-color: alpha(@card_bg_color, 0.72);
    outline: 1px solid alpha(@card_fg_color, 0.10);
    outline-offset: -1px;
    padding: 18px;
}
.accent-color-choice {
    min-width: 38px;
    min-height: 38px;
    padding: 4px;
    border-radius: 999px;
    background: transparent;
    box-shadow: none;
}
.accent-color-choice:hover {
    background-color: alpha(@window_fg_color, 0.08);
}
.accent-color-choice.accent-color-active {
    outline: 3px solid @accent_color;
    outline-offset: -3px;
}

/* ── Sub-abas de tipo de tema ────────────────────────────────────────── */
.kind-tab                   { border-radius: 8px; padding: 5px 14px; font-weight: 500; }
.kind-tab.kind-on           { background-color: alpha(@accent_bg_color, 0.18); color: @accent_color; font-weight: 700; }

/* ── Sub-abas de extensões ───────────────────────────────────────────── */
.sub-tab                    { border-radius: 8px; padding: 5px 14px; font-weight: 500; }
.sub-tab.sub-on             { background-color: alpha(@accent_bg_color, 0.18); color: @accent_color; font-weight: 700; }

/* ── Utilitários ─────────────────────────────────────────────────────── */
.page-title                 { font-weight: 800; letter-spacing: 0; }
.ok-col                     { color: @success_color; font-weight: 600; }
.err-col                    { color: @error_color; font-weight: 600; }
.mono                       { font-family: monospace; }
.global-btn                 { border-radius: 10px; padding: 7px 14px; font-weight: 600; }
.spinner-row                { border-radius: 10px; background-color: alpha(@accent_bg_color, 0.07); padding: 14px; }

/* ── Google Fonts ───────────────────────────────────────────────────── */
.google-font-search {
    min-height: 38px;
    border-radius: 9px;
}

/* ── Loading overlay (apply layout) ──────────────────────────────────── */
.loading-backdrop {
    background-color: alpha(black, 0.52);
    opacity: 0;
    transition: opacity 220ms ease;
}
.loading-backdrop.loading-show {
    opacity: 1;
}

.loading-card {
    background-color: alpha(#111318, 0.88);
    color: white;
    border-radius: 14px;
    padding: 22px 34px;
    min-width: 300px;
    min-height: 120px;
    box-shadow: 0 18px 46px alpha(black, 0.42),
                0 0 0 1px alpha(white, 0.10);
    opacity: 0;
    transition: opacity 240ms ease;
}
.loading-card.loading-show {
    opacity: 1;
}
.loading-art {
    margin-bottom: 2px;
    padding: 9px 12px;
    border-radius: 11px;
    background-image: linear-gradient(160deg,
                      alpha(#4a86e8, 0.16),
                      alpha(#2a3550, 0.04));
    box-shadow: inset 0 0 0 1px alpha(#6aa0ff, 0.24),
                0 0 24px alpha(#4a86e8, 0.18);
}
.loading-card label {
    font-weight: 600;
}
.loading-card spinner {
    color: white;
}
.loading-label {
    color: white;
}
"""
