// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {pathToFileURL} from 'node:url';

const root = process.env.BGC_RUNTIME_DIRECTORY
    ? pathToFileURL(`${process.env.BGC_RUNTIME_DIRECTORY}/`)
    : new URL('../usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/', import.meta.url);
const source = fs.readFileSync(new URL('dockSurface.js', root), 'utf8');
const names = ['_onDestroy', '_setupDockDwellIfNeeded', '_checkDockDwell',
    '_cancelDockDwell', '_dockDwellTimeout'];
const methods = names.map(name => {
    const match = source.match(new RegExp(`^    ${name}\\([^]*?^    }`, 'm'));
    assert.ok(match, name);
    return match[0];
}).join('\n');

function harness() {
    let nextId = 0, reveals = 0, watches = 0;
    const sources = new Map(), removed = [];
    const settings = {showDelay: 0.1, requirePressureToShow: false, autohideInFullscreen: false};
    const Main = {modalCount: 0, overview: {visible: false}, layoutManager: {
        getWorkAreaForMonitor: () => ({x: 0, y: 0, width: 800, height: 600}),
    }};
    const sharedGlobal = {display: {focus_window: {user_time: 4}}};
    const sandbox = {
        GLib: {PRIORITY_DEFAULT: 0, SOURCE_REMOVE: false,
            timeout_add(priority, delay, callback) { sources.set(++nextId, callback); return nextId; },
            source_remove(id) { removed.push(id); sources.delete(id); },
            Source: {set_name_by_id() {}},
        },
        DockSurfaceManager: {settings}, Main, global: sharedGlobal,
        St: {Side: {TOP: 0, RIGHT: 1, BOTTOM: 2, LEFT: 3}},
        Utils: {supportsExtendedBarriers: () => true},
        DOCK_DWELL_CHECK_INTERVAL: 100,
        PointerWatcher: {getPointerWatcher: () => ({
            addWatch() { watches++; return {}; },
            _removeWatch() { watches--; },
        })},
    };
    const Actor = vm.runInNewContext(`class Actor {${methods}}; Actor`, sandbox);
    const actor = new Actor();
    Object.assign(actor, {
        _position: 2, _monitor: {index: 0, x: 0, y: 0, width: 800, height: 600},
        _box: {hover: false}, _dockDwellTimeoutId: 0, _dockDwelling: false,
        _autohideIsEnabled: true, _onPressureSensed: () => reveals++,
        dash: {destroy() {}}, _intellihide: {destroy() {}},
        _themeManager: {destroy() {}}, _restoreUnredirect() {}, _removeBarrier() {},
    });
    return {actor, sources, removed, settings, Main, sharedGlobal,
        manager: sandbox.DockSurfaceManager,
        reveals: () => reveals, watches: () => watches,
        enter: () => actor._checkDockDwell(400, 599),
        fire(id) { const callback = sources.get(id); sources.delete(id); return callback(); },
    };
}

let count = 0;
const test = (name, run) => {
    if (process.env.BGC_TEST_CASE && process.env.BGC_TEST_CASE !== name) return;
    try { run(); count++; } catch (error) { error.message = `${name}: ${error.message}`; throw error; }
};
test('destroy cancels dwell before child cleanup', () => {
    const h = harness();
    h.enter();
    const id = h.actor._dockDwellTimeoutId;
    h.actor.dash.destroy = () => {
        assert.equal(h.sources.size, 0);
        assert.equal(h.actor._dockDwellTimeoutId, 0);
    };
    h.actor._onDestroy();
    assert.deepEqual(h.removed, [id]);
    assert.equal(h.reveals(), 0);
});
test('child cleanup failure leaves no dwell timer', () => {
    const h = harness();
    h.enter();
    h.actor.dash.destroy = () => { throw new Error('child'); };
    assert.throws(() => h.actor._onDestroy(), /child/);
    assert.equal(h.sources.size, 0);
});
test('retired callback never reads replacement settings', () => {
    const h = harness();
    h.enter();
    const callback = h.sources.get(h.actor._dockDwellTimeoutId);
    h.actor._onDestroy();
    Object.defineProperty(h.manager, 'settings', {get() { throw new Error('retired access'); }});
    assert.equal(callback(), false);
    h.enter();
    h.actor._setupDockDwellIfNeeded();
    assert.equal(h.actor._dockDwellTimeout(), false);
    assert.equal(h.sources.size, 0);
});
test('old callback cannot clear a replacement timer', () => {
    const h = harness();
    h.enter();
    const old = h.sources.get(h.actor._dockDwellTimeoutId);
    h.actor._checkDockDwell(200, 200);
    h.enter();
    const current = h.actor._dockDwellTimeoutId;
    assert.equal(old(), false);
    assert.equal(h.actor._dockDwellTimeoutId, current);
    assert.equal(h.reveals(), 0);
    h.fire(current);
    assert.equal(h.reveals(), 1);
});
for (const change of ['autohide', 'pressure', 'reconfigure']) {
    test(`reconfigure cancels dwell: ${change}`, () => {
        const h = harness();
        h.enter();
        const callback = h.sources.get(h.actor._dockDwellTimeoutId);
        if (change === 'autohide') h.actor._autohideIsEnabled = false;
        if (change === 'pressure') h.settings.requirePressureToShow = true;
        h.actor._setupDockDwellIfNeeded();
        assert.equal(h.sources.size, 0);
        assert.equal(callback(), false);
        assert.equal(h.reveals(), 0);
        assert.equal(h.watches(), change === 'reconfigure' ? 1 : 0);
    });
}
test('leaving the edge cancels dwell once', () => {
    const h = harness();
    h.enter();
    h.actor._checkDockDwell(200, 200);
    h.actor._cancelDockDwell();
    assert.equal(h.sources.size, 0);
    assert.equal(h.removed.length, 1);
});
test('one reveal per edge entry', () => {
    const h = harness();
    h.enter(); h.enter();
    assert.equal(h.sources.size, 1);
    h.fire(h.actor._dockDwellTimeoutId);
    h.enter();
    assert.equal(h.sources.size, 0);
    assert.equal(h.reveals(), 1);
    h.actor._checkDockDwell(200, 200);
    h.enter();
    h.fire(h.actor._dockDwellTimeoutId);
    assert.equal(h.reveals(), 2);
});
for (const blocked of ['hover', 'fullscreen', 'modal', 'interaction']) {
    test(`preserve reveal guard: ${blocked}`, () => {
        const h = harness();
        if (blocked === 'hover') h.actor._box.hover = true;
        h.enter();
        if (blocked === 'fullscreen') h.actor._monitor.inFullscreen = true;
        if (blocked === 'modal') h.Main.modalCount = 1;
        if (blocked === 'interaction') h.sharedGlobal.display.focus_window.user_time++;
        if (h.actor._dockDwellTimeoutId) h.fire(h.actor._dockDwellTimeoutId);
        assert.equal(h.reveals(), 0);
        assert.equal(h.actor._dockDwellTimeoutId, 0);
    });
}
for (const [side, x, y] of [[0, 400, 0], [1, 799, 300], [2, 400, 599], [3, 0, 300]]) {
    test(`reveal on side ${side}`, () => {
        const h = harness();
        h.actor._position = side;
        h.actor._checkDockDwell(x, y);
        assert.ok(h.actor._dockDwellTimeoutId);
        h.fire(h.actor._dockDwellTimeoutId);
        assert.equal(h.reveals(), 1);
    });
}
console.log(`${count} dock dwell lifecycle scenarios passed`);
