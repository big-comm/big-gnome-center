// SPDX-License-Identifier: MIT
// Common lifecycle for the current helper and its legacy UUID.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {ExtensionType} from 'resource:///org/gnome/shell/misc/extensionUtils.js';

const DISCOVERABLE_UUIDS = new Set([
    'layout-switcher-helper@communitybig.org',
    'layout-switcher-runtime@communitybig.org',
    'community-menu@communitybig.org',
    'big-shot@communitybig.org',
    'community-dock@communitybig.org',
    'community-panel@communitybig.org',
]);

const LIVE_STATES = new Set([1, 8]);
const STATE_ACTIVE = 1;
const STATE_ERROR = 3;
const STATE_DEACTIVATING = 7;
const STATE_WAIT_MS = 4000;
const STATE_POLL_MS = 50;

export class HelperLifecycle extends Extension {
    _busy() {
        return Boolean(this._switching || this._applying);
    }

    _returnJson(invocation, obj) {
        invocation.return_value(new GLib.Variant('(s)', [JSON.stringify(obj)]));
    }

    DiscoverExtensionsAsync(params, invocation) {
        const [payload] = params;
        this._discoverExtensions(payload)
            .then(result => this._returnJson(invocation, result))
            .catch(error => this._returnJson(invocation, {
                ok: false, loaded: [], missing: [], error: String(error),
            }));
    }

    async _discoverExtensions(payload) {
        const requested = [...new Set((JSON.parse(payload || '{}').uuids ?? [])
            .filter(uuid => DISCOVERABLE_UUIDS.has(uuid)))];
        const manager = Main.extensionManager;
        const loaded = [];
        const missing = [];
        const errors = [];

        for (const uuid of requested) {
            if (manager.lookup(uuid))
                continue;
            const dir = Gio.File.new_for_path(
                `/usr/share/gnome-shell/extensions/${uuid}`);
            if (!dir.query_exists(null)) {
                missing.push(uuid);
                continue;
            }
            try {
                const extension = manager.createExtensionObject(
                    uuid, dir, ExtensionType.SYSTEM);
                await manager.loadExtension(extension); // NOSONAR: S9382 - Shell extension transitions must run in order.
                loaded.push(uuid);
            } catch (error) {
                errors.push(`${uuid}: ${error}`);
            }
        }

        for (const uuid of requested) {
            if (!manager.lookup(uuid) && !missing.includes(uuid))
                missing.push(uuid);
        }
        return {
            ok: missing.length === 0 && errors.length === 0,
            loaded,
            missing,
            error: errors.join('; '),
        };
    }

    // disable() removes tracked sources; cancelled sleeps stay unresolved.
    _sleep(ms) {
        return new Promise(resolve => {
            const id = GLib.timeout_add(GLib.PRIORITY_DEFAULT, Math.max(0, ms | 0), () => {
                this._pendingSources?.delete(id);
                resolve();
                return GLib.SOURCE_REMOVE;
            });
            this._pendingSources?.add(id);
        });
    }

    _isDown(state) {
        return state === undefined ||
            (!LIVE_STATES.has(state) && state !== STATE_DEACTIVATING);
    }

    _isSettledUp(state) {
        // ERROR counts as settled: waiting longer won't fix it, and the
        // caller's self-heal pass handles it.
        return state === STATE_ACTIVE || state === STATE_ERROR;
    }

    _liveUuids(mgr) {
        const uuids = typeof mgr.getUuids === 'function'
            ? mgr.getUuids()
            : [...(mgr._extensions?.keys() ?? [])];
        const live = new Set();
        for (const uuid of uuids) {
            const ext = mgr.lookup(uuid);
            if (ext && LIVE_STATES.has(ext.state))
                live.add(uuid);
        }
        return live;
    }

    _orderedLive(mgr) {
        const live = this._liveUuids(mgr);
        const order = Array.isArray(mgr._extensionOrder) ? mgr._extensionOrder : [];
        const ordered = order.filter(u => live.has(u));
        for (const uuid of live) {
            if (!ordered.includes(uuid))
                ordered.push(uuid);
        }
        return ordered;
    }

    _moveExtensionLast(mgr, uuid) {
        const order = mgr._extensionOrder;
        if (!Array.isArray(order))
            return false;
        const idx = order.indexOf(uuid);
        if (idx < 0)
            return false;
        if (idx !== order.length - 1) {
            order.splice(idx, 1);
            order.push(uuid);
        }
        return true;
    }

    // Recheck on the Shell main loop until ready, cancelled, or timed out.
    async _waitUntil(ready, timeoutMs = STATE_WAIT_MS) {
        const deadline = GLib.get_monotonic_time() + timeoutMs * 1000;
        for (;;) {
            if (this._cancelled)
                return false;
            if (ready())
                return true;
            if (GLib.get_monotonic_time() >= deadline)
                return false;
            await this._sleep(STATE_POLL_MS); // NOSONAR: S9382 - polling must yield before rechecking Shell state.
        }
    }

    _waitState(manager, uuid, predicate, timeoutMs = STATE_WAIT_MS) {
        return this._waitUntil(() => predicate(manager.lookup(uuid)?.state), timeoutMs);
    }

    _waitDashToPanelReady(timeoutMs = STATE_WAIT_MS) {
        return this._waitUntil(() => global.dashToPanel?.panels?.some(
            panel => Boolean(panel?.taskbar?._box)), timeoutMs);
    }

    _prepareTeardown(manager, steps, rollbackSeconds) {
        const self = this._selfUuid();
        // Keep the helper ahead of Shell rebase cascades.
        if (Array.isArray(manager._extensionOrder)) {
            const index = manager._extensionOrder.indexOf(self);
            if (index > 0) {
                manager._extensionOrder.splice(index, 1);
                manager._extensionOrder.unshift(self);
                steps.push('hoist self');
            }
        }
        // Arm rollback before the first extension is disabled.
        this._prevEnabled = this._orderedLive(manager);
        this._armRollbackTimer(rollbackSeconds);
        return this._prevEnabled.filter(uuid => uuid !== self).reverse();
    }
}
