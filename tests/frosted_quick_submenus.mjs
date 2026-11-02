// SPDX-License-Identifier: MIT
// Actors disposed by the Shell (submenus, logout teardown) are never touched again.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const file = new URL(
    '../usr/share/gnome-shell/extensions/frosted-glass@communitybig.org/shellSurfaces.js',
    import.meta.url);
const source = fs.readFileSync(file, 'utf8')
    .replace(/^import .*;$/gm, '').replace(/^export /gm, '');

let nextId = 0;
class Actor {
    constructor() {
        this.classes = new Set();
        this.signals = new Map();
        this.disposed = false;
        this.touches = 0;
    }

    _use() {
        this.touches++;
        if (this.disposed)
            throw new Error('Object has been already disposed');
    }

    has_style_class_name(name) { this._use(); return this.classes.has(name); }
    add_style_class_name(name) { this._use(); this.classes.add(name); }
    remove_style_class_name(name) { this._use(); this.classes.delete(name); }
    connect(signal, callback) { this.signals.set(++nextId, {signal, callback}); return nextId; }
    disconnect(id) { this._use(); this.signals.delete(id); }
    dispose() {
        for (const {signal, callback} of [...this.signals.values()])
            if (signal === 'destroy') callback(this);
        this.signals.clear();
        this.disposed = true;
    }
}

const sources = new Map();
const GLib = {
    PRIORITY_DEFAULT: 0,
    PRIORITY_DEFAULT_IDLE: 200,
    SOURCE_REMOVE: false,
    SOURCE_CONTINUE: true,
    timeout_add_seconds(_priority, _seconds, callback) { sources.set(++nextId, callback); return nextId; },
    idle_add(_priority, callback) { sources.set(++nextId, callback); return nextId; },
    source_remove(id) { sources.delete(id); },
};
const Main = {uiGroup: null, layoutManager: {}, panel: null};
const ShellSurfaces = vm.runInNewContext(`${source}\n;ShellSurfaces`, {
    GLib,
    Main,
    ShellBlurSurface: class {},
    console: {warn() {}, debug() {}},
});

// A live submenu is styled, then restored with its destroy watch released.
const surfaces = new ShellSurfaces(() => ({}));
const live = new Actor();
live.classes.add('popup-menu');
surfaces._syncQuickSubmenus(new Set([live]), false);
assert.ok(live.classes.has('frosted-glass-quick-submenu'));
assert.equal(live.signals.size, 1);
surfaces._syncQuickSubmenus(new Set(), false);
assert.deepEqual([...live.classes], ['popup-menu']);
assert.equal(live.signals.size, 0);
assert.equal(surfaces._quickSubmenus.size, 0);

// A submenu the Shell disposes (logout, panel rebuild) is forgotten at once.
const doomed = new Actor();
surfaces._syncQuickSubmenus(new Set([doomed]), true);
assert.equal(surfaces._quickSubmenus.size, 1);
doomed.dispose();
assert.equal(surfaces._quickSubmenus.size, 0);
const touches = doomed.touches;
surfaces._syncQuickSubmenus(new Set(), false);
surfaces.destroy();
assert.equal(doomed.touches, touches, 'disposed submenu was accessed again');

// Logout disposes the Shell UI with extensions still enabled: scanning stops
// and no tracked actor is touched afterwards.
Main.uiGroup = new Actor();
const shell = new ShellSurfaces(() => ({enabled: false}));
shell.enable();
assert.ok(shell._scanId, 'periodic scan is scheduled');
const submenu = new Actor();
shell._syncQuickSubmenus(new Set([submenu]), false);
const before = submenu.touches;
Main.uiGroup.dispose();
assert.equal(sources.size, 0, 'refresh sources survive Shell teardown');
assert.equal(shell._quickSubmenus.size, 0);
shell.refresh();
shell.destroy();
assert.equal(submenu.touches, before, 'actor touched after Shell teardown');

console.log('frosted quick submenu lifecycle passed');
