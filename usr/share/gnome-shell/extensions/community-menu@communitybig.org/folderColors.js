// SPDX-License-Identifier: GPL-2.0-or-later
import GLib from 'gi://GLib';

import {FOLDER_COLORS} from './deskUxModel.js';
import {validFolderId} from './folderModel.js';
import {createMenuSettings} from './settings.js';

const supported = color => FOLDER_COLORS.some(([name]) => name === color);

export class FolderColors {
    constructor(changed, settings = null) {
        this._ownsSettings = settings === null;
        this._settings = settings ?? createMenuSettings('org.gnome.shell.extensions.community-menu.folders');
        this._signals = [
            this._settings.connect('changed::colors', changed),
            this._settings.connect('writable-changed::colors', changed),
        ];
    }

    get writable() {
        return this._settings.is_writable('colors');
    }

    get(id) {
        const color = this._snapshot().get(id);
        return supported(color) ? color : null;
    }

    _snapshot() {
        const value = this._settings.get_value('colors');
        return new Map(Array.from({length: value.n_children()},
            (_unused, index) => value.get_child_value(index).deep_unpack()));
    }

    set(id, color) {
        if (!this.writable || !validFolderId(id) || (color !== null && !supported(color)))
            return false;
        const colors = this._snapshot();
        if (color === null)
            colors.delete(id);
        else
            colors.set(id, color);
        return this._settings.set_value('colors', new GLib.Variant('a{ss}', Object.fromEntries(colors)));
    }

    destroy() {
        if (this._destroyed) return;
        this._destroyed = true;
        for (const signal of this._signals)
            this._settings.disconnect(signal);
        this._signals = [];
        if (this._ownsSettings) this._settings.run_dispose?.();
    }
}
