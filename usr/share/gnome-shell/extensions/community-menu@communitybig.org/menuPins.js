// SPDX-License-Identifier: GPL-2.0-or-later
import Gio from 'gi://Gio';
import {createMenuSettings} from './settings.js';

export class MenuPins {
    constructor(changed = () => {}, settings = null, legacy = null) {
        this._settings = settings ?? createMenuSettings('org.gnome.shell.extensions.community-menu.pins');
        // An explicit empty list is final; never repopulate it from the dock.
        if (this._settings.get_user_value('apps') === null && this.writable) {
            const shell = legacy ?? new Gio.Settings({schema_id: 'org.gnome.shell'});
            this._write(shell.get_strv('favorite-apps'));
        }
        this._signals = [
            this._settings.connect('changed::apps', changed),
            this._settings.connect('writable-changed::apps', changed),
        ];
    }

    get writable() {
        return this._settings.is_writable('apps');
    }

    ids() {
        return this._settings.get_strv('apps');
    }

    has(id) {
        return this.ids().includes(id);
    }

    add(ids) {
        return this._write([...this.ids(), ...ids]);
    }

    remove(id) {
        return this._write(this.ids().filter(item => item !== id));
    }

    move(id, before = null) {
        if (id === before)
            return false;
        const ids = this.ids().filter(item => item !== id);
        const position = ids.indexOf(before);
        ids.splice(position < 0 ? ids.length : position, 0, id);
        return this._write(ids);
    }

    _write(ids) {
        if (!this.writable)
            return false;
        return this._settings.set_strv('apps', [...new Set(ids)]);
    }

    destroy() {
        if (this._destroyed) return;
        this._destroyed = true;
        for (const signal of this._signals)
            this._settings.disconnect(signal);
        this._signals = [];
    }
}
