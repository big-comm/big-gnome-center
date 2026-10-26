// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
import vm from 'node:vm';

const root = process.env.BGC_RUNTIME_DIRECTORY
    ? pathToFileURL(`${process.env.BGC_RUNTIME_DIRECTORY}/`)
    : new URL('../usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/', import.meta.url);
const source = fs.readFileSync(new URL('regionUpdateWatchdog.js', root), 'utf8')
    .replace(/^import .*;$/gm, '').replaceAll('export ', '');

// A fake Shell: _queueUpdateRegions() and _updateRegions() behave as in
// GNOME Shell's layout.js; laterRuns() is the next frame running the later.
function harness({withUpdateRegions = true, monitorManager = true} = {}) {
    const timers = new Map(), warnings = [];
    let nextId = 0, nextLater = 100;
    class Emitter {
        constructor() { this.signals = new Map(); }
        connect(signal, callback) { this.signals.set(++nextId, {signal, callback}); return nextId; }
        disconnect(id) {
            if (this.failDisconnect)
                throw new Error('injected disconnect failure');
            this.signals.delete(id);
        }
        emit(signal) { for (const s of [...this.signals.values()]) if (s.signal === signal) s.callback(); }
    }
    const layout = Object.assign(new Emitter(), {
        _updateRegionIdle: 0,
        updates: 0,
        removedLaters: [],
        _queueUpdateRegions() {
            if (!this._updateRegionIdle)
                this._updateRegionIdle = ++nextLater;
        },
        _updateRegions() {
            if (this.failUpdate)
                throw new Error('injected update failure');
            if (this._updateRegionIdle) {
                this.removedLaters.push(this._updateRegionIdle);
                delete this._updateRegionIdle;
            }
            this.updates++;
            return false;
        },
        laterRuns() { if (this._updateRegionIdle) this._updateRegions(); },
    });
    if (!withUpdateRegions)
        delete layout._updateRegions;
    const monitors = monitorManager ? new Emitter() : null;
    const add = (seconds, callback, priority) => {
        timers.set(++nextId, {seconds, callback, priority});
        return nextId;
    };
    const GLib = {
        PRIORITY_LOW: 300, PRIORITY_DEFAULT: 0, SOURCE_REMOVE: false, SOURCE_CONTINUE: true,
        timeout_add_seconds: (priority, seconds, callback) => add(seconds, callback, priority),
        source_remove: id => { assert.ok(timers.delete(id), `source ${id} removed twice`); },
        get_real_time: () => 42,
    };
    const Watchdog = vm.runInNewContext(`${source}\nRegionUpdateWatchdog`, {
        GLib,
        Main: {layoutManager: layout},
        global: {backend: {get_monitor_manager: () => monitors}},
        console: {warn: message => warnings.push(message)},
    });
    // Fire every pending timer that waits `seconds`; repeating ones stay.
    const tick = seconds => {
        for (const [id, timer] of [...timers]) {
            if (timer.seconds !== seconds || !timers.has(id))
                continue;
            if (timer.callback() !== true)
                timers.delete(id);
        }
    };
    return {watchdog: new Watchdog(), layout, monitors, timers, tick, warnings};
}

let checks = 0;
function test(name, run) {
    try {
        run();
        checks++;
    } catch (error) {
        throw new Error(name, {cause: error});
    }
}

test('a later stuck across a monitor change is run once', () => {
    const {watchdog: w, layout, tick, warnings} = harness();
    w.enable();
    layout._queueUpdateRegions();
    const stuck = layout._updateRegionIdle;
    layout.emit('monitors-changed');
    tick(2);
    assert.equal(layout.updates, 1);
    assert.deepEqual(layout.removedLaters, [stuck]);
    assert.equal(layout._updateRegionIdle, undefined);
    assert.equal(w.diagnostics().repairs, 1);
    assert.deepEqual({...w.diagnostics().lastRepair}, {id: stuck, time: 42});
    assert.equal(warnings.length, 1);
    // Shell can queue again, and the next later runs normally.
    layout._queueUpdateRegions();
    assert.notEqual(layout._updateRegionIdle, stuck);
    w.destroy();
});

test('a later that runs on the next frame is left alone', () => {
    const {watchdog: w, layout, tick} = harness();
    w.enable();
    layout._queueUpdateRegions();
    layout.emit('monitors-changed');
    layout.laterRuns();
    tick(2);
    assert.equal(layout.updates, 1);
    assert.equal(w.diagnostics().repairs, 0);
    w.destroy();
});

test('a new later queued after the change is not mistaken for the old one', () => {
    const {watchdog: w, layout, tick} = harness();
    w.enable();
    layout._queueUpdateRegions();
    layout.emit('monitors-changed');
    layout.laterRuns();
    layout._queueUpdateRegions();
    tick(2);
    assert.equal(w.diagnostics().repairs, 0);
    assert.equal(w.diagnostics().pending, layout._updateRegionIdle);
    w.destroy();
});

test('nothing pending means nothing to do', () => {
    const {watchdog: w, layout, tick} = harness();
    w.enable();
    layout.emit('monitors-changed');
    tick(2);
    tick(30);
    tick(30);
    assert.equal(layout.updates, 0);
    w.destroy();
});

test('enabling looks for a later left stuck while locked', () => {
    const {watchdog: w, layout, tick} = harness();
    layout._queueUpdateRegions();
    w.enable();
    tick(2);
    assert.equal(w.diagnostics().repairs, 1);
    w.destroy();
});

test('a power-save change triggers a check', () => {
    const {watchdog: w, layout, monitors, tick} = harness();
    w.enable();
    tick(2);
    layout._queueUpdateRegions();
    monitors.emit('power-save-mode-changed');
    tick(2);
    assert.equal(w.diagnostics().repairs, 1);
    w.destroy();
});

test('the periodic check catches a later stuck without any event', () => {
    const {watchdog: w, layout, tick} = harness();
    w.enable();
    tick(2);
    layout._queueUpdateRegions();
    tick(30);
    assert.equal(w.diagnostics().repairs, 0);
    tick(30);
    assert.equal(w.diagnostics().repairs, 1);
    w.destroy();
});

test('back-to-back events keep a single recheck', () => {
    const {watchdog: w, layout, timers, tick} = harness();
    w.enable();
    layout._queueUpdateRegions();
    for (let i = 0; i < 5; i++)
        layout.emit('monitors-changed');
    assert.equal([...timers.values()].filter(t => t.seconds === 2).length, 1);
    tick(2);
    assert.equal(w.diagnostics().repairs, 1);
    w.destroy();
});

test('a failing repair is counted and does not throw', () => {
    const {watchdog: w, layout, tick, warnings} = harness();
    w.enable();
    layout._queueUpdateRegions();
    layout.failUpdate = true;
    layout.emit('monitors-changed');
    tick(2);
    assert.equal(w.diagnostics().failures, 1);
    assert.equal(w.diagnostics().repairs, 0);
    assert.match(warnings[0], /repair failed/);
    layout.failUpdate = false;
    layout.emit('monitors-changed');
    tick(2);
    assert.equal(w.diagnostics().repairs, 1);
    w.destroy();
});

test('destroy removes every source and signal, and can run twice', () => {
    const {watchdog: w, layout, monitors, timers, tick} = harness();
    w.enable();
    layout.emit('monitors-changed');
    w.destroy();
    assert.equal(timers.size, 0);
    assert.equal(layout.signals.size, 0);
    assert.equal(monitors.signals.size, 0);
    assert.equal(w.diagnostics().active, false);
    layout._queueUpdateRegions();
    layout.emit('monitors-changed');
    tick(2);
    tick(30);
    assert.equal(layout.updates, 0);
    w.destroy();
});

test('destroy carries on after a disconnect failure', () => {
    const {watchdog: w, layout, monitors, timers, warnings} = harness();
    w.enable();
    layout.failDisconnect = true;
    w.destroy();
    assert.equal(warnings.length, 1);
    assert.equal(monitors.signals.size, 0);
    assert.equal(timers.size, 0);
});

test('enabling twice does not double the watch', () => {
    const {watchdog: w, layout, timers} = harness();
    w.enable();
    w.enable();
    assert.equal(layout.signals.size, 1);
    assert.equal([...timers.values()].filter(t => t.seconds === 30).length, 1);
    w.destroy();
    w.enable();
    assert.equal(layout.signals.size, 1);
    w.destroy();
});

test('a Shell without _updateRegions leaves the watchdog off', () => {
    const {watchdog: w, layout, timers} = harness({withUpdateRegions: false});
    w.enable();
    assert.equal(timers.size, 0);
    assert.equal(layout.signals.size, 0);
    assert.equal(w.diagnostics().active, false);
    w.destroy();
});

test('works without a monitor manager', () => {
    const {watchdog: w, layout, tick} = harness({monitorManager: false});
    w.enable();
    layout._queueUpdateRegions();
    layout.emit('monitors-changed');
    tick(2);
    assert.equal(w.diagnostics().repairs, 1);
    w.destroy();
});

console.log(`${checks} region update watchdog scenarios passed`);
