// SPDX-License-Identifier: GPL-2.0-or-later

import * as Utils from './taskbar/utils.js';

const MODES = new Set(['always-visible', 'always-hidden', 'intelligent']);

export class TaskbarVisibilityModes {
    constructor(settings) {
        this._settings = settings;
    }

    apply(mode) {
        const selected = MODES.has(mode) ? mode : 'always-visible';
        const intelligent = selected === 'intelligent';
        // Explicit runtime changes must not inherit the upstream startup delay.
        this._settings.set_int('intellihide-enable-start-delay', 0);
        this._settings.set_boolean('intellihide-only-secondary', false);
        this._settings.set_boolean('intellihide-hide-from-windows', intelligent);
        this._settings.set_boolean('intellihide-hide-from-monitor-windows', false);
        this._settings.set_string('intellihide-behaviour', 'FOCUSED_WINDOWS');
        this._settings.set_boolean('intellihide-use-pointer', true);
        // Enable last: Intellihide reads the delay and behavior during enable().
        this._settings.set_boolean('intellihide', selected !== 'always-visible');
    }

    mode() {
        if (!this._settings.get_boolean('intellihide'))
            return 'always-visible';
        if (this._settings.get_boolean('intellihide-hide-from-windows') ||
            this._settings.get_boolean('intellihide-hide-from-monitor-windows'))
            return 'intelligent';
        return 'always-hidden';
    }

    panelState(panel) {
        const actor = panel?.panelBox;
        const tracked = actor ? Utils.getTrackedActorData(actor) : null;
        return {
            intellihideEnabled: Boolean(panel?.intellihide?.enabled),
            affectsStruts: Boolean(tracked?.affectsStruts),
            holdStatus: panel?.intellihide?._holdStatus ?? 0,
            translationX: Math.round(actor?.translation_x ?? 0),
            translationY: Math.round(actor?.translation_y ?? 0),
        };
    }

}
