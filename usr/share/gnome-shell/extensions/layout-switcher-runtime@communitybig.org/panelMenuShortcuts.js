// SPDX-License-Identifier: GPL-2.0-or-later

export class PanelMenuShortcuts {
    constructor(panel, reveal) {
        this._panel = panel;
        this._reveal = reveal;
        this._descriptor = Object.getOwnPropertyDescriptor(panel, '_toggleMenu');
        const original = panel._toggleMenu;
        const owner = this;
        this._toggle = function (indicator) {
            const activePanel = owner._panel;
            if (activePanel && indicator?.reactive && indicator.menu &&
                (indicator === activePanel.statusArea.dateMenu ||
                 indicator === activePanel.statusArea.quickSettings))
                owner._reveal();
            return original.call(this, indicator);
        };
        panel._toggleMenu = this._toggle;
    }

    destroy() {
        const panel = this._panel;
        this._panel = null;
        this._reveal = null;
        if (!panel || panel._toggleMenu !== this._toggle)
            return;
        if (this._descriptor)
            Object.defineProperty(panel, '_toggleMenu', this._descriptor);
        else
            delete panel._toggleMenu;
    }
}
