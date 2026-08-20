// SPDX-License-Identifier: GPL-3.0-or-later

import Meta from 'gi://Meta';

import {BlurSurface} from './blurSurface.js';
import {ConnectionManager} from './connectionManager.js';

const WINDOW_TYPES = new Set([
    Meta.WindowType.NORMAL,
    Meta.WindowType.DIALOG,
    Meta.WindowType.MODAL_DIALOG,
]);

export class WindowController {
    constructor(getConfig) {
        this._getConfig = getConfig;
        this._connections = new ConnectionManager();
        this._windows = new Map();
        this._destroyed = false;
    }

    enable() {
        this._connections.connect(global.display, 'window-created',
            () => this._queueRefresh());
        this._connections.connect(global.display, 'restacked',
            () => this.refresh());
        this.refresh();
    }

    refresh() {
        if (this._destroyed)
            return;
        const config = this._getConfig();
        const actors = new Set(global.get_window_actors());

        for (const [actor, record] of this._windows) {
            if (!actors.has(actor) || !config.enabled || !config.windowsEnabled ||
                this._isExcluded(actor.meta_window, config.exclusions)) {
                this._destroyRecord(actor, record);
            }
        }

        if (!config.enabled || !config.windowsEnabled)
            return;

        for (const actor of actors)
            this._updateWindow(actor, config);
    }

    destroy() {
        this._destroyed = true;
        this._connections.disconnectAll();
        for (const [actor, record] of [...this._windows])
            this._destroyRecord(actor, record);
    }

    _updateWindow(actor, config) {
        const metaWindow = actor.meta_window;
        if (!metaWindow || !WINDOW_TYPES.has(metaWindow.get_window_type()) ||
            metaWindow.is_override_redirect() ||
            this._isExcluded(metaWindow, config.exclusions))
            return;

        const behavior = metaWindow.is_fullscreen()
            ? config.fullscreenBehavior
            : metaWindow.is_maximized()
                ? config.maximizedBehavior
                : 'keep';

        let record = this._windows.get(actor);
        if (!record) {
            const connections = new ConnectionManager();
            for (const signal of [
                'notify::fullscreen',
                'notify::maximized-horizontally',
                'notify::maximized-vertically',
                'notify::wm-class',
                'size-changed',
                'position-changed',
            ]) {
                connections.connect(metaWindow, signal, () => this.refresh());
            }
            connections.connect(actor, 'destroy', () => {
                connections.disconnectAll();
                this._windows.delete(actor);
            });
            record = {surface: null, connections};
            this._windows.set(actor, record);
        }

        if (behavior === 'disable') {
            record.surface?.destroy();
            record.surface = null;
            return;
        }

        if (!record.surface) {
            record.surface = new BlurSurface(actor, {
                kind: 'window',
                contentOpacity: true,
                cornerRadius: 14,
                maskCorners: false,
                geometryProvider: () => this._windowGeometry(metaWindow),
            });
        }

        record.surface.update(config);
        record.surface.setOpaque(behavior === 'opaque');
    }

    _destroyRecord(actor, record) {
        record.connections.disconnectAll();
        record.surface?.destroy();
        this._windows.delete(actor);
    }

    _isExcluded(metaWindow, exclusions) {
        const identities = [
            metaWindow?.get_wm_class?.(),
            metaWindow?.get_wm_class_instance?.(),
            metaWindow?.get_gtk_application_id?.(),
        ].filter(Boolean).map(value => value.toLowerCase());

        return exclusions.some(exclusion => {
            const needle = exclusion.trim().toLowerCase();
            return needle && identities.some(identity =>
                identity === needle || identity.includes(needle));
        });
    }

    _windowGeometry(metaWindow) {
        const frame = metaWindow.get_frame_rect();
        const buffer = metaWindow.get_buffer_rect();
        return {
            x: frame.x - buffer.x,
            y: frame.y - buffer.y,
            width: frame.width,
            height: frame.height,
        };
    }

    _queueRefresh() {
        global.compositor.get_laters().add(Meta.LaterType.BEFORE_REDRAW, () => {
            if (!this._destroyed)
                this.refresh();
            return false;
        });
    }
}
