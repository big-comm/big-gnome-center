// SPDX-License-Identifier: GPL-2.0-or-later

import {Hold} from './taskbar/intellihide.js';

export class TaskbarInteractions {
    constructor() {
        this._records = new Map();
        this._panelOpenCounts = new Map();
        this._created = {preview: 0, context: 0};
    }

    adoptPreviewMenu(panel, menu) {
        return this._track(menu, panel, 'preview');
    }

    createContextMenu(icon, factory) {
        return this._track(factory(), icon.dtpPanel, 'context');
    }

    diagnostics() {
        const records = [...this._records.values()];
        return {
            previewMenus: records.filter(record => record.kind === 'preview').length,
            contextMenus: records.filter(record => record.kind === 'context').length,
            openMenus: records.filter(record => record.open).length,
            heldPanels: this._panelOpenCounts.size,
            created: {...this._created},
        };
    }

    destroy() {
        for (const [menu, record] of this._records) {
            this._disconnect(menu, record.stateId);
            this._disconnect(record.destroyTarget, record.destroyId);
            if (record.open)
                this._release(record.panel);
        }
        this._records.clear();
        for (const panel of this._panelOpenCounts.keys())
            panel.intellihide?.release(Hold.MENU);
        this._panelOpenCounts.clear();
    }

    _track(menu, panel, kind) {
        const destroyTarget = menu.actor ?? menu;
        const record = {
            panel,
            kind,
            open: false,
            stateId: menu.connect('open-state-changed', (_menu, open) =>
                this._setOpen(menu, typeof open === 'boolean' ? open : this._isOpen(menu))),
            destroyTarget,
            destroyId: destroyTarget.connect('destroy', () => this._forget(menu)),
        };
        this._records.set(menu, record);
        this._created[kind]++;
        return menu;
    }

    _setOpen(menu, open) {
        const record = this._records.get(menu);
        if (!record || record.open === open)
            return;
        record.open = open;
        if (open)
            this._hold(record.panel);
        else
            this._release(record.panel);
    }

    _forget(menu) {
        const record = this._records.get(menu);
        if (!record)
            return;
        if (record.open)
            this._release(record.panel);
        this._records.delete(menu);
    }

    _hold(panel) {
        const count = this._panelOpenCounts.get(panel) ?? 0;
        if (!count)
            panel.intellihide?.revealAndHold(Hold.MENU);
        this._panelOpenCounts.set(panel, count + 1);
    }

    _release(panel) {
        const count = this._panelOpenCounts.get(panel) ?? 0;
        if (count <= 1) {
            this._panelOpenCounts.delete(panel);
            panel.intellihide?.release(Hold.MENU);
        } else {
            this._panelOpenCounts.set(panel, count - 1);
        }
    }

    _isOpen(menu) {
        return Boolean(menu.opened ?? menu.isOpen);
    }

    _disconnect(object, id) {
        if (!object || !id)
            return;
        try {
            object.disconnect(id);
        } catch (_error) {
            // The inherited owner may already have destroyed the actor.
        }
    }
}
