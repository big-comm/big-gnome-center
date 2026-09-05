// SPDX-License-Identifier: GPL-2.0-or-later

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {ControlsState} from 'resource:///org/gnome/shell/ui/overviewControls.js';

const SESSION_MARKER = 'layoutSwitcherStartupOverviewHandled';

export class StartupOverviewIntegration {
    constructor() {
        this._originalHasOverview = Main.sessionMode.hasOverview;
        this._startupCompleteId = 0;
        this._ownedValue = null;
        this._skipRequested = false;
        this._applied = false;
        this._restored = false;
        this._restoreConflicts = 0;
        this._lastConflict = '';
        this._postStartupHide = false;
        this._firstSessionActivation = !global[SESSION_MARKER];
        global[SESSION_MARKER] = true;
    }

    apply(skip) {
        this._skipRequested = Boolean(skip);
        if (!Main.layoutManager._startingUp) {
            if (this._firstSessionActivation && this._skipRequested)
                this._finishStartup();
            this._firstSessionActivation = false;
            return;
        }
        this._firstSessionActivation = false;

        if (!this._startupCompleteId) {
            this._startupCompleteId = Main.layoutManager.connect(
                'startup-complete',
                () => this._onStartupComplete(),
            );
        }

        const value = this._skipRequested ? false : this._originalHasOverview;
        this._recordConflict('apply');
        Main.sessionMode.hasOverview = value;
        this._ownedValue = value;
        this._applied = true;
        this._restored = false;
    }

    destroy() {
        if (this._startupCompleteId) {
            Main.layoutManager.disconnect(this._startupCompleteId);
            this._startupCompleteId = 0;
        }
        this._restore('destroy');
    }

    diagnostics() {
        return {
            implementation: 'layout-switcher-runtime',
            connected: Boolean(this._startupCompleteId),
            startingUp: Boolean(Main.layoutManager._startingUp),
            skipRequested: this._skipRequested,
            applied: this._applied,
            restored: this._restored,
            postStartupHide: this._postStartupHide,
            restorationPending: Boolean(this._startupCompleteId),
            restoreConflicts: this._restoreConflicts,
            lastConflict: this._lastConflict,
        };
    }

    _onStartupComplete() {
        const id = this._startupCompleteId;
        this._startupCompleteId = 0;
        if (id)
            Main.layoutManager.disconnect(id);
        this._restore('startup-complete');
        if (this._skipRequested)
            this._finishStartup();
    }

    _finishStartup() {
        if (Main.overview.visible || Main.overview.visibleTarget) {
            Main.overview.hide();
            this._postStartupHide = true;
        } else {
            // Skipping Shell's startup overview leaves its adjustment at WINDOW_PICKER.
            const adjustment = Main.overview._overview?.controls?._stateAdjustment;
            if (adjustment) {
                adjustment.remove_transition('value');
                adjustment.value = ControlsState.HIDDEN;
            }
        }
        this._applied = true;
        this._restored = true;
    }

    _restore(reason) {
        if (this._ownedValue === null)
            return;
        this._recordConflict(reason);
        if (Main.sessionMode.hasOverview === this._ownedValue)
            Main.sessionMode.hasOverview = this._originalHasOverview;
        this._ownedValue = null;
        this._restored = true;
    }

    _recordConflict(reason) {
        if (this._ownedValue === null ||
            Main.sessionMode.hasOverview === this._ownedValue)
            return;
        this._restoreConflicts++;
        this._lastConflict = reason;
    }
}
