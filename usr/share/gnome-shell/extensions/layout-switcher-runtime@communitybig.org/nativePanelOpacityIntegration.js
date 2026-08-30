// SPDX-License-Identifier: GPL-2.0-or-later

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

export class NativePanelOpacityIntegration {
    constructor() {
        this._panel = null;
        this._originalStyle = null;
        this._ownedStyle = null;
        this._opacity = null;
        this._styleChangedId = 0;
        this._applying = false;
        this._externalStyleUpdates = 0;
        this._repairCount = 0;
        this._restoreConflicts = 0;
        this._lastConflict = '';
    }

    activate(opacity) {
        if (!Number.isInteger(opacity)) {
            this.deactivate();
            return;
        }

        const panel = Main.panel;
        if (this._panel && this._panel !== panel)
            this.deactivate();
        if (!this._panel) {
            this._panel = panel;
            this._originalStyle = panel.get_style();
            this._captureBackground();
            this._styleChangedId = panel.connect(
                'notify::style', () => this._onStyleChanged());
        }

        this._opacity = Math.max(0, Math.min(100, opacity));
        this._applyStyle();
    }

    _captureBackground() {
        const color = this._panel.get_theme_node().get_background_color();
        this._background = [color.red, color.green, color.blue];
    }

    _applyStyle() {
        const base = this._originalStyle?.trim() ?? '';
        const separator = base && !base.endsWith(';') ? '; ' : base ? ' ' : '';
        const [red, green, blue] = this._background;
        this._ownedStyle = `${base}${separator}background-color: rgba(` +
            `${red}, ${green}, ${blue}, ${(this._opacity / 100).toFixed(2)});`;
        this._applying = true;
        try {
            this._panel.set_style(this._ownedStyle);
        } finally {
            this._applying = false;
        }
    }

    _onStyleChanged() {
        if (this._applying || !this._panel)
            return;
        const style = this._panel.get_style();
        if (style === this._ownedStyle)
            return;
        this._externalStyleUpdates++;
        this._originalStyle = style;
        this._captureBackground();
        this._repairCount++;
        this._applyStyle();
    }

    deactivate() {
        if (!this._panel)
            return;
        if (this._styleChangedId)
            this._panel.disconnect(this._styleChangedId);
        this._styleChangedId = 0;
        if (this._panel.get_style() === this._ownedStyle) {
            this._panel.set_style(this._originalStyle);
        } else {
            this._restoreConflicts++;
            this._lastConflict = 'native panel inline style changed externally';
        }
        this._panel = null;
        this._originalStyle = null;
        this._ownedStyle = null;
        this._opacity = null;
        this._background = null;
    }

    destroy() {
        this.deactivate();
    }

    diagnostics() {
        const active = Boolean(this._panel);
        const effectiveOpacity = active
            ? Math.round(this._panel.get_theme_node().get_background_color().alpha / 255 * 100)
            : null;
        return {
            implementation: 'layout-switcher-runtime',
            active,
            opacity: this._opacity,
            effectiveOpacity,
            styleOwned: active && this._panel.get_style() === this._ownedStyle,
            styleSignalOwned: active && Boolean(this._styleChangedId),
            externalStyleUpdates: this._externalStyleUpdates,
            repairCount: this._repairCount,
            restorationPending: active,
            restoreConflicts: this._restoreConflicts,
            lastConflict: this._lastConflict,
        };
    }
}
