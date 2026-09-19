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
        this._unredirectDisabled = false;
        this._enabled = false;
        zone.reactive = false;
        this._pressure = null;
        this._barrier = null;
        this._barrierRelease = 0;
        this._targetVisible = false;
        this._dwell = 0;
        this._animationGeneration = 0;
        this._enterId = 0;
        this._leaveId = 0;
        try {
            this._enterId = zone.connect('enter-event', () => this._enter());
            this._leaveId = zone.connect('leave-event', () => this._cancelDwell());
        } catch (error) {
            this.destroy();
            throw error;
        }
    }

    setEnabled(enabled) {
        if (this._destroyed || this._enabled === enabled)
            return;
        this._enabled = enabled;
        this._zone.reactive = enabled;
        this.reposition();
    }

    reposition() {
        if (this._destroyed)
            return;
        this._cancelDwell();
        this._clearBarrier();
        const monitor = Main.layoutManager.primaryMonitor;
        this._zone.reactive = this._enabled && !this._targetVisible;
        if (!this._enabled || this._targetVisible || !monitor ||
            !(global.backend.capabilities & Meta.BackendCapabilities.BARRIERS))
            return;
        try {
            this._createBarrier(monitor);
        } catch (error) {
            this._clearBarrier();
            throw error;
        }
    }

    _createBarrier(monitor) {
        const pressure = this._pressure = new Layout.PressureBarrier(100, 1000, Shell.ActionMode.NORMAL);
        this._barrier = new Meta.Barrier({
            backend: global.backend,
            x1: monitor.x,
            x2: monitor.x + monitor.width,
            y1: monitor.y,
            y2: monitor.y,
            directions: Meta.BarrierDirection.POSITIVE_Y,
        });
        this._pressure.addBarrier(this._barrier);
        pressure.connect('trigger', () => {
            if (!this._destroyed && this._enabled && this._pressure === pressure)
                this._reveal();
        });
        this._zone.reactive = false;
    }

    _enter() {
        if (this._destroyed || !this._enabled || this._pressure || this._dwell)
            return;
        // Backends without pointer barriers still require deliberate dwell.
        const id = this._dwell = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 250, () => {
            if (this._destroyed || this._dwell !== id)
                return GLib.SOURCE_REMOVE;
            this._dwell = 0;
            if (this._enabled && this._zone.hover)
                this._reveal();
            return GLib.SOURCE_REMOVE;
        });
    }

    _cancelDwell() {
        const id = this._dwell;
        this._dwell = 0;
        if (id)
            this._cleanup(() => GLib.Source.remove(id));
    }

    _clearBarrier() {
        this._cancelBarrierRelease();
        const pressure = this._pressure;
        const barrier = this._barrier;
        this._pressure = null;
        this._barrier = null;
        this._cleanup(() => pressure?.destroy());
        this._cleanup(() => barrier?.destroy());
    }

    _cancelBarrierRelease() {
        const id = this._barrierRelease;
        this._barrierRelease = 0;
        if (id)
            this._cleanup(() => GLib.Source.remove(id));
    }

    _syncBarrier() {
        if (this._destroyed)
            return;
        if (!this._targetVisible) {
            this.reposition();
        } else if (this._barrier && !this._barrierRelease) {
            // Release cross-monitor movement after the reveal settles.
            const id = this._barrierRelease = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 100, () => {
                if (this._destroyed || this._barrierRelease !== id)
                    return GLib.SOURCE_REMOVE;
                this._barrierRelease = 0;
                this._clearBarrier();
                return GLib.SOURCE_REMOVE;
            });
        }
    }

    pointerInside() {
        if (this._destroyed)
            return false;
        const [x, y] = global.get_pointer();
        const monitor = Main.layoutManager.primaryMonitor;
        if (!monitor || !this._actor.visible)
            return false;
        // Include the reveal strip and panel margins, which do not report panel hover.
        return x >= monitor.x && x < monitor.x + monitor.width &&
            y >= monitor.y && y < monitor.y + Math.max(2, this._actor.height);
    }

    _setComposited(composited) {
        if (this._unredirectDisabled === composited)
            return;
        if (composited)
            global.compositor.disable_unredirect();
        else
            global.compositor.enable_unredirect();
        this._unredirectDisabled = composited;
    }

    setVisible(visible, immediate = false) {
        if (this._destroyed)
            return;
        const actor = this._actor;
        this._targetVisible = visible;
        if (!visible)
            this._cancelBarrierRelease();
        // Keep overlays composited until their hide animation completes.
        if (visible || actor.visible)
            this._setComposited(true);
        this._zone.reactive = this._enabled && !visible && !this._pressure;
        const destination = visible
            ? this._originalTranslation
            : this._originalTranslation - Math.max(1, actor.height);
        if (this._destination === destination && actor.visible === visible &&
            !immediate)
            return;
        if (this._destination === destination && actor.get_transition('translation-y') &&
            !immediate)
            return;
        const generation = ++this._animationGeneration;
        actor.remove_transition('translation-y');
        this._destination = destination;
        if (visible && !actor.visible)
            actor.translation_y = this._originalTranslation - Math.max(1, actor.height);
        if (immediate || (!visible && !actor.visible)) {
            actor.translation_y = destination;
            actor.visible = visible;
            if (!visible)
                this._setComposited(false);
            this._syncBarrier();
            Main.layoutManager._queueUpdateRegions();
            return;
        }
        actor.show();
        actor.ease({
            translation_y: destination,
            duration: 200,
            mode: Clutter.AnimationMode.EASE_OUT_QUAD,
            onComplete: () => {
                if (this._destroyed || this._animationGeneration !== generation)
                    return;
                actor.visible = visible;
                if (!visible)
                    this._setComposited(false);
                this._syncBarrier();
                Main.layoutManager._queueUpdateRegions();
            },
        });
    }

    destroy() {
        if (this._destroyed)
            return;
        this._destroyed = true;
        this._enabled = false;
        this._animationGeneration++;
        this._cancelDwell();
        this._clearBarrier();
        for (const id of [this._enterId, this._leaveId]) {
            if (id)
                this._cleanup(() => this._zone.disconnect(id));
        }
        this._enterId = this._leaveId = 0;
        this._cleanup(() => { this._zone.reactive = false; });
        this._cleanup(() => this._actor.remove_transition('translation-y'));
        this._cleanup(() => { this._actor.translation_y = this._originalTranslation; });
        this._cleanup(() => this._setComposited(false));
        this._actor = this._zone = this._reveal = null;
    }

    _cleanup(callback) {
        try {
            callback();
        } catch (error) {
            console.warn(`[layout-switcher-runtime] Panel autohide cleanup failed: ${error}`);
        }
    }
}
