// SPDX-License-Identifier: GPL-2.0-or-later

export class PanelMenuShortcuts {
    constructor(panel, reveal) {
        this._panel = panel;
        this._descriptor = Object.getOwnPropertyDescriptor(panel, '_toggleMenu');
        const original = panel._toggleMenu;
        this._toggle = function (indicator) {
            if (indicator?.reactive && indicator.menu &&
                (indicator === panel.statusArea.dateMenu ||
                 indicator === panel.statusArea.quickSettings))
                reveal();
            return original.call(this, indicator);
        };
        panel._toggleMenu = this._toggle;
    }

    destroy() {
        if (this._panel._toggleMenu !== this._toggle)
            return;
        if (this._descriptor)
            Object.defineProperty(this._panel, '_toggleMenu', this._descriptor);
        else
            delete this._panel._toggleMenu;
    }
}
