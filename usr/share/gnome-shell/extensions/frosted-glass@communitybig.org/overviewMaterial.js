// SPDX-License-Identifier: GPL-3.0-or-later

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';

const CACHE_DIRECTORY = 'communitybig-frosted-glass';
const CACHE_FILENAME = 'overview-material.css';
const UPDATE_DELAY_MS = 120;

function clamp(value, minimum = 0, maximum = 1) {
    return Math.min(maximum, Math.max(minimum, value));
}

export function materialColor(config, opacity, neutral = [128, 130, 138]) {
    const alpha = clamp(opacity);
    if (config.useAccentColor)
        return `st-transparentize(-st-accent-color, ${(1 - alpha).toFixed(3)})`;
    return `rgba(${neutral.join(', ')}, ${alpha.toFixed(3)})`;
}

function selectorGroup(selectors, declarations) {
    const qualified = selectors.map(selector =>
        `.frosted-glass-overview.frosted-glass-overview ${selector}`
    );
    return `${qualified.join(',\n')} {\n${declarations}\n}`;
}

function materialStylesheet(config) {
    const base = clamp(config.materialOpacity);
    const hover = clamp(base + 0.12);
    const focus = clamp(base + 0.22);
    const active = clamp(base + 0.30);
    const foreground = config.useAccentColor
        ? '-st-accent-fg-color'
        : config.lightMode ? '#2e2e33' : 'white';
    const focusBorder = config.useAccentColor
        ? 'st-transparentize(-st-accent-fg-color, 0.55)'
        : 'rgba(255, 255, 255, 0.28)';

    return [
        selectorGroup([
            '.search-entry',
            '.workspace-thumbnail',
            '.search-section-content',
            '.overview-tile.app-folder',
        ], `  background-color: ${materialColor(config, base)} !important;`),
        selectorGroup([
            '.search-entry',
            '.search-section-content',
            '.overview-tile.app-folder',
        ], `  color: ${foreground} !important;`),
        selectorGroup([
            '.overview-tile:hover',
            '.grid-search-result:hover',
            '.list-search-result:hover',
            '.search-provider-icon:hover',
            '.overview-tile.app-folder:hover',
        ], `  background-color: ${materialColor(config, hover, [148, 150, 158])} !important;`),
        selectorGroup([
            '.overview-tile:focus',
            '.overview-tile:highlighted',
            '.overview-tile:selected',
            '.overview-tile:checked',
            '.grid-search-result:focus',
            '.grid-search-result:highlighted',
            '.grid-search-result:selected',
            '.grid-search-result:checked',
            '.list-search-result:focus',
            '.list-search-result:highlighted',
            '.list-search-result:selected',
            '.list-search-result:checked',
            '.search-provider-icon:focus',
            '.search-provider-icon:highlighted',
            '.search-provider-icon:selected',
            '.search-provider-icon:checked',
            '.overview-tile.app-folder:focus',
            '.overview-tile.app-folder:selected',
            '.overview-tile.app-folder:highlighted',
        ], [
            `  background-color: ${materialColor(config, focus, [168, 170, 178])} !important;`,
            `  border-color: ${focusBorder} !important;`,
        ].join('\n')),
        selectorGroup([
            '.overview-tile:active',
            '.grid-search-result:active',
            '.list-search-result:active',
            '.search-provider-icon:active',
            '.overview-tile.app-folder:active',
            '.overview-tile.app-folder:focus:hover',
            '.overview-tile.app-folder:drop',
        ], `  background-color: ${materialColor(config, active, [188, 190, 198])} !important;`),
    ].join('\n\n');
}

export class OverviewMaterialStylesheet {
    constructor() {
        const directory = GLib.build_filenamev([GLib.get_user_cache_dir(), CACHE_DIRECTORY]);
        GLib.mkdir_with_parents(directory, 0o700);
        this._file = Gio.File.new_for_path(GLib.build_filenamev([directory, CACHE_FILENAME]));
        this._theme = null;
        this._loaded = false;
        this._content = '';
        this._updateId = 0;
    }

    update(config) {
        const content = materialStylesheet(config);
        if (content === this._content) {
            if (this._updateId) {
                GLib.source_remove(this._updateId);
                this._updateId = 0;
            }
            return;
        }

        if (!this._loaded) {
            this._apply(content);
            return;
        }
        if (this._updateId)
            GLib.source_remove(this._updateId);
        this._updateId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, UPDATE_DELAY_MS, () => {
            this._updateId = 0;
            this._apply(content);
            return GLib.SOURCE_REMOVE;
        });
    }

    _apply(content) {
        this._unload();
        GLib.file_set_contents(this._file.get_path(), content);
        this._theme = St.ThemeContext.get_for_stage(global.stage).get_theme();
        this._theme.load_stylesheet(this._file);
        this._loaded = true;
        this._content = content;
    }

    destroy() {
        if (this._updateId) {
            GLib.source_remove(this._updateId);
            this._updateId = 0;
        }
        this._unload();
        try {
            if (this._file.query_exists(null))
                this._file.delete(null);
        } catch (error) {
            console.debug(`Frosted Glass: cannot remove material stylesheet: ${error}`);
        }
        this._content = '';
        this._file = null;
    }

    _unload() {
        if (!this._loaded)
            return;
        try {
            this._theme?.unload_stylesheet(this._file);
        } catch (error) {
            console.debug(`Frosted Glass: cannot unload material stylesheet: ${error}`);
        }
        this._theme = null;
        this._loaded = false;
    }
}
