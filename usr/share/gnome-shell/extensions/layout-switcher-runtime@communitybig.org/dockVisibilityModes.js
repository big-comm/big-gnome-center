// SPDX-License-Identifier: GPL-2.0-or-later

const MODES = new Set([
    'always-visible',
    'always-hidden',
    'intelligent',
]);

export class DockVisibilityModes {
    constructor(settings) {
        this._settings = settings;
    }

    apply(mode) {
        const selected = MODES.has(mode) ? mode : 'intelligent';
        this._settings.set_boolean('manualhide', false);
        this._settings.set_boolean('dock-fixed', selected === 'always-visible');
        this._settings.set_boolean('intellihide', selected === 'intelligent');
        this._settings.set_boolean('autohide', selected !== 'always-visible');
    }

    mode() {
        if (this._settings.get_boolean('dock-fixed'))
            return 'always-visible';
        if (this._settings.get_boolean('intellihide'))
            return 'intelligent';
        return 'always-hidden';
    }

    runtimeState() {
        if (this._settings.get_boolean('dock-fixed') ||
            this._settings.get_boolean('manualhide')) {
            return {autohide: false, intellihide: false};
        }
        return {
            autohide: this._settings.get_boolean('autohide'),
            intellihide: this._settings.get_boolean('intellihide'),
        };
    }
}
