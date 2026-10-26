// SPDX-License-Identifier: GPL-2.0-or-later

import GLib from 'gi://GLib';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

// GNOME Shell recomputes the space the panel and the dock reserve on screen
// (struts, and so the work area) in one BEFORE_REDRAW later. It keeps that
// later's id in LayoutManager._updateRegionIdle and queues no other while the
// id is set. On real hardware the later has been seen to never run after
// monitor and power changes: the work area then stays frozen and maximized
// windows go under a dock that should push them up, until the session ends.
// A later runs on the next frame, so the same one still pending seconds
// later is stuck; run the update it was meant to run.
const RECHECK_SECONDS = 2;
const PERIODIC_SECONDS = 30;

export class RegionUpdateWatchdog {
    constructor() {
        this._signals = [];
        this._recheckId = 0;
        this._periodicId = 0;
        this._suspect = 0;
        this._repairs = 0;
        this._failures = 0;
        this._lastRepair = null;
    }

    enable() {
        if (this._periodicId || typeof Main.layoutManager?._updateRegions !== 'function')
            return;

        this._connect(Main.layoutManager, 'monitors-changed');
        this._connect(global.backend?.get_monitor_manager?.(), 'power-save-mode-changed');
        this._periodicId = GLib.timeout_add_seconds(
            GLib.PRIORITY_LOW, PERIODIC_SECONDS, () => {
                this._check();
                return GLib.SOURCE_CONTINUE;
            });
        // The runtime is disabled on the lock screen and enabled again on
        // unlock, so this also looks at every unlock.
        this._watch();
    }

    destroy() {
        for (const [object, id] of this._signals.splice(0)) {
            try {
                object.disconnect(id);
            } catch (error) {
                console.warn(`[layout-switcher-runtime] region watchdog cleanup failed: ${error}`);
            }
        }
        for (const property of ['_recheckId', '_periodicId']) {
            if (this[property])
                GLib.source_remove(this[property]);
            this[property] = 0;
        }
        this._suspect = 0;
    }

    diagnostics() {
        return {
            implementation: 'layout-switcher-runtime',
            active: Boolean(this._periodicId),
            pending: this._pending(),
            repairs: this._repairs,
            failures: this._failures,
            lastRepair: this._lastRepair,
        };
    }

    _connect(object, signal) {
        if (!object)
            return;
        this._signals.push([object, object.connect(signal, () => this._watch())]);
    }

    _pending() {
        return Main.layoutManager?._updateRegionIdle || 0;
    }

    // Note the later pending now; if it is still the pending one when the
    // recheck runs, it never ran.
    _watch() {
        this._suspect = this._pending();
        if (this._recheckId)
            GLib.source_remove(this._recheckId);
        this._recheckId = GLib.timeout_add_seconds(
            GLib.PRIORITY_DEFAULT, RECHECK_SECONDS, () => {
                this._recheckId = 0;
                this._check();
                return GLib.SOURCE_REMOVE;
            });
    }

    _check() {
        const pending = this._pending();
        if (pending && pending === this._suspect)
            this._repair(pending);
        this._suspect = this._pending();
    }

    _repair(id) {
        try {
            // Removes the stuck later itself before recomputing the regions.
            Main.layoutManager._updateRegions();
            this._repairs++;
            this._lastRepair = {id, time: GLib.get_real_time()};
            console.warn(`[layout-switcher-runtime] Shell region update ${id} never ran; ran it now`);
        } catch (error) {
            this._failures++;
            console.warn(`[layout-switcher-runtime] region update repair failed: ${error}`);
        }
    }
}
