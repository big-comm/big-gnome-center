// SPDX-License-Identifier: GPL-2.0-or-later
// GNOME 51 removed ui/pointerWatcher.js; use compositor cursor notifications.
import GLib from 'gi://GLib';
import * as Config from 'resource:///org/gnome/shell/misc/config.js';

export class CursorWatcher {
    constructor() {
        this._watches = new Set();
        this._tracker = null;
        this._signal = 0;
    }

    addWatch(interval, callback) {
        const watch = {
            callback, interval: Math.max(1, interval), pending: 0,
            remove: () => this._removeWatch(watch),
        };
        this._watches.add(watch);
        if (!this._signal) {
            this._tracker = global.backend.get_cursor_tracker();
            this._signal = this._tracker.connect('position-invalidated', () => {
                for (const entry of this._watches) {
                    if (entry.pending)
                        continue;
                    entry.pending = GLib.timeout_add(
                        GLib.PRIORITY_DEFAULT, entry.interval, () => {
                            entry.pending = 0;
                            const [x, y] = global.get_pointer();
                            entry.callback(x, y);
                            return GLib.SOURCE_REMOVE;
                        });
                }
            });
        }
        return watch;
    }

    _removeWatch(watch) {
        if (!this._watches.delete(watch))
            return;
        if (watch.pending) {
            GLib.source_remove(watch.pending);
            watch.pending = 0;
        }
        if (!this._watches.size && this._signal) {
            this._tracker.disconnect(this._signal);
            this._signal = 0;
            this._tracker = null;
        }
    }
}

const legacy = Number.parseInt(Config.PACKAGE_VERSION, 10) < 51
    ? await import('resource:///org/gnome/shell/ui/pointerWatcher.js')
    : null;
let watcher;

export function getPointerWatcher() {
    return legacy ? legacy.getPointerWatcher() : (watcher ??= new CursorWatcher());
}
