// SPDX-License-Identifier: GPL-2.0-or-later

import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';

import * as Layout from 'resource:///org/gnome/shell/ui/layout.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

export class PanelAutohide {
    constructor(actor, zone, reveal) {
        this._actor = actor;
        this._zone = zone;
        this._reveal = reveal;
        this._originalTranslation = actor.translation_y;
        this._destination = null;
        this._enabled = false;
        zone.reactive = false;
        this._pressure = null;
        this._barrier = null;
        this._dwell = 0;
        this._enterId = zone.connect('enter-event', () => this._enter());
        this._leaveId = zone.connect('leave-event', () => this._cancelDwell());
    }

    setEnabled(enabled) {
        if (this._enabled === enabled)
            return;
        this._enabled = enabled;
        this._zone.reactive = enabled;
        this.reposition();
    }

    reposition() {
        this._cancelDwell();
        this._clearBarrier();
        const monitor = Main.layoutManager.primaryMonitor;
        if (!this._enabled || !monitor ||
            !(global.backend.capabilities & Meta.BackendCapabilities.BARRIERS))
            return;
        this._pressure = new Layout.PressureBarrier(100, 1000, Shell.ActionMode.NORMAL);
        this._barrier = new Meta.Barrier({
            backend: global.backend,
            x1: monitor.x,
            x2: monitor.x + monitor.width,
            y1: monitor.y,
            y2: monitor.y,
            directions: Meta.BarrierDirection.POSITIVE_Y,
        });
        this._pressure.addBarrier(this._barrier);
        this._pressure.connect('trigger', () => this._reveal());
    }

    _enter() {
        if (!this._enabled || this._pressure || this._dwell)
            return;
        // Backends without pointer barriers still require deliberate dwell.
        this._dwell = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 250, () => {
            this._dwell = 0;
            if (this._enabled && this._zone.hover)
                this._reveal();
            return GLib.SOURCE_REMOVE;
        });
    }

    _cancelDwell() {
        if (this._dwell)
            GLib.Source.remove(this._dwell);
        this._dwell = 0;
    }

    _clearBarrier() {
        this._pressure?.destroy();
        this._barrier?.destroy();
        this._pressure = null;
        this._barrier = null;
    }

    setVisible(visible, immediate = false) {
        const actor = this._actor;
        const destination = visible
            ? this._originalTranslation
            : this._originalTranslation - Math.max(1, actor.height);
        if (this._destination === destination && actor.visible === visible &&
            !immediate)
            return;
        if (this._destination === destination && actor.get_transition('translation-y') &&
            !immediate)
            return;
        actor.remove_transition('translation-y');
        this._destination = destination;
        if (visible && !actor.visible)
            actor.translation_y = this._originalTranslation - Math.max(1, actor.height);
        if (immediate || (!visible && !actor.visible)) {
            actor.translation_y = destination;
            actor.visible = visible;
            Main.layoutManager._queueUpdateRegions();
            return;
        }
        actor.show();
        actor.ease({
            translation_y: destination,
            duration: 200,
            mode: Clutter.AnimationMode.EASE_OUT_QUAD,
            onComplete: () => {
                actor.visible = visible;
                Main.layoutManager._queueUpdateRegions();
            },
        });
    }

    destroy() {
        this._cancelDwell();
        this._clearBarrier();
        this._zone.disconnect(this._enterId);
        this._zone.disconnect(this._leaveId);
        this._actor.remove_transition('translation-y');
        this._actor.translation_y = this._originalTranslation;
    }
}
